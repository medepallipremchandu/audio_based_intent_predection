INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key = 'feedback.analysis.view'
WHERE r.name = 'resolver'
ON CONFLICT DO NOTHING;
