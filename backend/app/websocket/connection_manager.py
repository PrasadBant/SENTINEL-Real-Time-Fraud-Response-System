"""
SENTINEL — WebSocket Connection Manager
=========================================
Tracks connected dashboard clients and broadcasts events to all of them.
A single module-level `manager` instance is shared across every router
that needs to push live updates (transactions, cases, actions).

Each process's `active_connections` is necessarily process-local — a
live WebSocket object can't cross a process boundary. What used to be
process-local *fanout* (broadcast() looping over that list directly) is
now Redis pub/sub: broadcast() only publishes, and every process
(including the one that published — a deliberate self-subscribe, so
there's no special-casing between "one replica" and "many replicas")
receives the message back through listen() and delivers it to its own
active_connections. This is what makes a broadcast from one API replica
actually reach a client connected to a different replica.

Phase 2 hostile-review fix (CRITICAL): fanout is now tenant-scoped at the
Redis pub/sub layer, not just filtered in application code after the
fact. Every tenant gets its own channel (`sentinel:broadcast:{tenant_id}`)
— broadcast() takes tenant_id and only ever publishes to that one
channel; active_connections is keyed by tenant_id (dict[str,
list[WebSocket]]), not a single flat list, so delivery iterates ONLY the
sub-list for the message's own tenant. This is a structural guarantee,
not a filter that can be silently forgotten later: a bug in delivery
code would have to explicitly reach into another tenant's key in the
dict to leak across tenants, rather than merely omitting an `if` check
against a flat shared list (which is exactly how the pre-fix version
leaked — every connected socket, any tenant, received every message).
listen() dynamically subscribes to a new tenant's channel the moment
that tenant's first WebSocket connects on this process (see connect()),
and re-subscribes to every tenant currently in active_connections on
each reconnect cycle (self-healing after a Redis outage without needing
a separate "known tenants" list to survive it).

Both broadcast() and listen() are resilient to Redis being unreachable
(Phase 1 hostile-review findings): broadcast() logs and returns rather
than raising, so a Redis outage degrades live-update delivery instead of
turning every POST /transaction/action into a 500; listen() wraps its
subscribe loop in a bounded-exponential-backoff reconnect loop, since a
Redis restart was found (by direct reproduction — killing a live Redis
mid-stream) to kill the listener permanently otherwise — redis-py
resubscribes automatically on a *proactive* reconnect (the next command
issued through a connection) but does not resume an in-flight
`pubsub.listen()` generator after it raises ConnectionError.
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

from app.core import redis_client

logger = logging.getLogger("sentinel.websocket")

CHANNEL_PREFIX = "sentinel:broadcast:"

# Bounded exponential backoff for listen()'s reconnect loop.
_INITIAL_RECONNECT_DELAY = 1.0
_MAX_RECONNECT_DELAY = 30.0


def channel_for(tenant_id: str) -> str:
    return f"{CHANNEL_PREFIX}{tenant_id}"


# A permanent, never-published-to placeholder channel that listen()
# always subscribes to, in addition to whatever real tenant channels are
# currently active. Without this, a listen() cycle that starts with zero
# WebSocket connections yet (the normal cold-start case — nobody has
# connected before the listener task boots) would call pubsub.listen()
# with ZERO subscriptions. Confirmed empirically: fakeredis's async
# PubSub.listen() simply returns immediately when there's nothing
# subscribed, rather than blocking — which turned the reconnect loop's
# `while True` into an unthrottled busy-loop (thousands of "reconnects"
# per second, no backoff ever engaged, since a clean generator exit
# isn't the `except Exception` path that applies backoff). Always having
# at least this one subscription guarantees pubsub.listen() always has
# something to block on.
_KEEPALIVE_CHANNEL = f"{CHANNEL_PREFIX}__keepalive__"


class ConnectionManager:
    def __init__(self) -> None:
        # tenant_id -> the list of this process's live sockets for that
        # tenant. A dict, not one flat list — see module docstring for
        # why this shape is itself part of the tenant-isolation fix, not
        # just an implementation detail.
        self.active_connections: dict[str, list[WebSocket]] = {}
        # The PubSub object listen() currently holds, so connect() can
        # add a live subscription for a brand-new tenant without waiting
        # for the next reconnect cycle. None whenever listen() isn't
        # currently connected (startup, or mid-backoff after an outage);
        # connect() degrades to "this tenant's messages arrive once
        # listen() reconnects" in that window, same posture as every
        # other Redis-outage degradation in this module.
        self._pubsub: Any = None
        # Serializes: (a) concurrent connect() calls each trying to
        # SUBSCRIBE on the same shared PubSub connection (redis-py's
        # PubSub.subscribe() only *sends* the command without waiting for
        # the reply — see its docstring — so concurrent sends without a
        # lock could interleave on the wire), and (b) a connect() call
        # racing listen()'s own reconnect cycle while it's replacing
        # self._pubsub.
        self._pubsub_lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, tenant_id: str) -> None:
        await websocket.accept()
        is_first_for_tenant = tenant_id not in self.active_connections
        self.active_connections.setdefault(tenant_id, []).append(websocket)
        if is_first_for_tenant:
            async with self._pubsub_lock:
                if self._pubsub is not None:
                    try:
                        await self._pubsub.subscribe(channel_for(tenant_id))
                    except Exception as e:
                        # Degrades safely: listen()'s own reconnect loop
                        # re-subscribes to every tenant still present in
                        # active_connections (this one included) the next
                        # time it (re)establishes a connection, so this
                        # tenant isn't permanently missed — just delayed
                        # until that happens.
                        logger.warning("Live subscribe failed for tenant %s: %s", tenant_id, e)

    def disconnect(self, websocket: WebSocket, tenant_id: str) -> None:
        conns = self.active_connections.get(tenant_id)
        if not conns:
            return
        remaining = [ws for ws in conns if ws is not websocket]
        if remaining:
            self.active_connections[tenant_id] = remaining
        else:
            # No unsubscribe call here on purpose: unsubscribing then
            # immediately needing to re-subscribe if another socket for
            # the same tenant connects moments later is a race not worth
            # taking on for a purely cosmetic cleanup — an idle
            # subscription with zero local sockets costs nothing (there's
            # nothing in active_connections to deliver to, so messages on
            # it are just dropped by _deliver_local below) and every
            # reconnect cycle naturally re-derives the correct
            # subscription set from active_connections anyway.
            del self.active_connections[tenant_id]

    async def broadcast(self, message: dict[str, Any], tenant_id: str) -> None:
        """Publish to this tenant's own Redis channel ONLY — delivery to
        local sockets happens in listen() below, even for the process
        that published (self-subscribe).

        tenant_id is required, not optional with a fallback: every call
        site must be explicit about whose event this is, exactly like
        app.core.repository's tenant-scoped read methods — an implicit
        "just use the default" here would silently re-introduce a
        cross-tenant leak the moment a second tenant exists.

        Does not raise on a Redis failure: every caller (POST /transaction,
        the action endpoints, attack-mode, the EC-03 job, the global-graph
        analyzer) treats a broadcast as a best-effort side effect of work
        that already succeeded (scoring, a Postgres write, a freeze) — a
        lost live-update notification should never turn that success into
        an HTTP 500."""
        try:
            await redis_client.get_async_redis().publish(channel_for(tenant_id), json.dumps(message, default=str))
        except Exception as e:
            logger.warning("broadcast degraded (Redis unavailable): %s", e)

    async def _deliver_local(self, tenant_id: str, message: dict[str, Any]) -> None:
        """Fan out to this process's own connections for ONE tenant only
        — the actual tenant-isolation enforcement point. Iterates
        active_connections[tenant_id], never the full active_connections
        dict, so there is no shared list a forgotten filter could leak
        from."""
        conns = self.active_connections.get(tenant_id, [])
        failed: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                failed.append(ws)
        for ws in failed:
            self.disconnect(ws, tenant_id)

    async def listen(self) -> None:
        """Long-running task (started in main.py's lifespan): subscribes to
        every tenant currently represented in active_connections and
        delivers each tenant's messages — including this same process's
        own publishes — to that tenant's local connections only. Runs
        until cancelled at shutdown.

        Wrapped in an outer reconnect loop with bounded exponential
        backoff: a dropped/restarted Redis connection kills the inner
        `pubsub.listen()` generator (it raises ConnectionError rather than
        transparently resuming), so without this the whole live-update
        pipeline would die silently and permanently until the API process
        itself was restarted — confirmed by directly killing a live Redis
        mid-stream during testing. Each reconnect attempt re-creates the
        PubSub object and re-subscribes to every tenant currently in
        active_connections from scratch, since the server-side
        subscription state is gone once the connection drops — this also
        means a reconnect naturally self-heals the subscription set to
        match reality (a tenant that disconnected during the outage isn't
        resubscribed; one that connected via connect()'s live-subscribe
        path, below, already is).
        """
        backoff = _INITIAL_RECONNECT_DELAY
        while True:
            try:
                pubsub = redis_client.get_async_redis().pubsub()
                tenants_snapshot = list(self.active_connections.keys())
                await pubsub.subscribe(_KEEPALIVE_CHANNEL, *[channel_for(t) for t in tenants_snapshot])
                async with self._pubsub_lock:
                    self._pubsub = pubsub
                logger.info("Subscribed to %d tenant channel(s)", len(tenants_snapshot))
                backoff = _INITIAL_RECONNECT_DELAY  # reset once a connection actually succeeds
                try:
                    async for msg in pubsub.listen():
                        if msg.get("type") not in ("message", "pmessage"):
                            continue
                        channel = msg.get("channel") or ""
                        if not channel.startswith(CHANNEL_PREFIX):
                            continue
                        tenant_id = channel[len(CHANNEL_PREFIX):]
                        try:
                            payload = json.loads(msg["data"])
                        except Exception:
                            continue
                        await self._deliver_local(tenant_id, payload)
                finally:
                    async with self._pubsub_lock:
                        self._pubsub = None
                    try:
                        await pubsub.unsubscribe()
                        await pubsub.aclose()
                    except Exception:
                        pass  # connection may already be broken — nothing more to clean up
            except asyncio.CancelledError:
                # Deliberate shutdown (main.py cancels this task) — not a
                # connection failure. Let it propagate; do not "reconnect"
                # from a cancellation. (CancelledError subclasses
                # BaseException, not Exception, since Python 3.8, so the
                # `except Exception` below would never catch it anyway —
                # this branch is here to make that intent explicit rather
                # than rely on that fact being known.)
                raise
            except Exception as e:
                logger.warning(
                    "WS pub/sub listener disconnected (%s) — reconnecting in %.1fs",
                    e, backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_RECONNECT_DELAY)


# Shared singleton — every router imports this same instance.
manager = ConnectionManager()
