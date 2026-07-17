let activeRole = localStorage.getItem('sentinel_role');

export const getRole = () => activeRole;

export const setRoleGlobal = (newRole) => {
  activeRole = newRole;
  localStorage.setItem("sentinel_role", newRole);
  window.location.reload(); 
};
