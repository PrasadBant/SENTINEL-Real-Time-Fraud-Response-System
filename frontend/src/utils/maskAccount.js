export const maskAccount = (acc) => {
  if (!acc) return "";
  const clean = acc.replace(/-/g, "");
  const last3 = clean.slice(-3);
  return `xxx-xxx-xxx-xxx-${last3}`;
};
