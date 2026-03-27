INSERT INTO permissions (key, label, tab_key) VALUES
('feedback.sensitive.mask', 'Mask sensitive data in UI', 'feedback_board')
ON CONFLICT (key) DO NOTHING;

-- Default: mask sensitive data for student/tracker/resolver roles (admins can opt-in if desired)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key = 'feedback.sensitive.mask'
WHERE r.name IN ('student', 'tracker', 'resolver')
ON CONFLICT DO NOTHING;
