INSERT INTO permissions (key, label, description, tab_key)
VALUES
('users.delete', 'Delete Users', 'Allows permanently deleting user accounts.', 'admin'),
('roles.delete', 'Delete Roles', 'Allows permanently deleting roles and their role-permission mappings.', 'admin')
ON CONFLICT (key) DO UPDATE SET
  label = EXCLUDED.label,
  description = EXCLUDED.description,
  tab_key = EXCLUDED.tab_key;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key IN ('users.delete', 'roles.delete')
WHERE r.name IN ('superadmin', 'admin')
ON CONFLICT DO NOTHING;
