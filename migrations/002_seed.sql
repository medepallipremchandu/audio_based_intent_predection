INSERT INTO permissions (key, label, tab_key) VALUES
('system.superadmin', 'Full System Access', 'admin'),
('roles.view', 'View roles', 'admin'),
('roles.manage', 'Create/update roles', 'admin'),
('roles.delete', 'Delete Roles', 'admin'),
('permissions.view', 'View permissions', 'admin'),
('permissions.manage', 'Create permissions', 'admin'),
('users.view', 'View users', 'admin'),
('users.manage', 'Manage users', 'admin'),
('users.delete', 'Delete Users', 'admin'),
('feedback.create', 'Submit Feedback', 'submit'),
('feedback.read_own', 'View Own Feedback', 'my_feedback'),
('feedback.read_all', 'View All Feedback', 'feedback_board'),
('feedback.read_assigned', 'View Assigned Feedback Only', 'feedback_board'),
('feedback.update', 'Update feedback status', 'feedback_board'),
('feedback.assign', 'Assign Feedback Owner', 'feedback_board'),
('feedback.analysis.view', 'View Analysis Details', 'feedback_board'),
('feedback.transcript.original.view', 'View Original Transcript', 'feedback_board'),
('feedback.sensitive.view', 'View Sensitive Content', 'feedback_board'),
('feedback.submitter.view', 'View Submitter Name', 'feedback_board'),
('dashboard.view', 'View dashboard', 'dashboard')
ON CONFLICT (key) DO NOTHING;

INSERT INTO roles (name, description) VALUES
('superadmin', 'Full control of roles and permissions')
ON CONFLICT (name) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON 1=1
WHERE r.name = 'superadmin'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key IN ('users.view', 'users.delete', 'roles.delete', 'feedback.read_all', 'feedback.update', 'feedback.submitter.view', 'dashboard.view')
WHERE r.name = 'admin'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key IN ('feedback.analysis.view', 'feedback.transcript.original.view', 'feedback.sensitive.view')
WHERE r.name = 'admin'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key IN ('feedback.create', 'feedback.read_own', 'dashboard.view')
WHERE r.name = 'student'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key IN ('feedback.read_assigned', 'feedback.update', 'feedback.submitter.view', 'dashboard.view')
WHERE r.name = 'resolver'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key IN ('feedback.analysis.view')
WHERE r.name = 'resolver'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key IN ('feedback.read_all', 'feedback.assign', 'feedback.submitter.view', 'dashboard.view')
WHERE r.name = 'tracker'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key IN ('feedback.analysis.view', 'feedback.transcript.original.view')
WHERE r.name = 'tracker'
ON CONFLICT DO NOTHING;

-- default superadmin password: SuperAdmin@123
INSERT INTO users (name, email, password_hash, is_active)
VALUES ('Super Admin', 'superadmin@local.dev', 'pbkdf2_sha256$390000$0123456789abcdeffedcba9876543210$2360c7d6b980e5840502e97d2d9d21f4ff11a8d5ca71b2c34ccf1cdd12598423', TRUE)
ON CONFLICT (email) DO NOTHING;

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u
JOIN roles r ON r.name = 'superadmin'
WHERE u.email = 'superadmin@local.dev'
ON CONFLICT DO NOTHING;
