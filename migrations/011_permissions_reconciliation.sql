-- Reconciliation migration:
-- Keeps historical migrations intact, but makes final permission catalog and grants
-- deterministic in one place for both fresh setups and existing databases.

ALTER TABLE permissions ADD COLUMN IF NOT EXISTS description TEXT;

-- 1) Canonical permission catalog (final labels/descriptions/tab mappings)
INSERT INTO permissions (key, label, description, tab_key)
VALUES
('system.superadmin', 'Full System Access', 'Grants unrestricted access to all protected features, routes, and admin actions.', 'admin'),
('roles.view', 'View Roles', 'Allows viewing role list, role details, and assigned permissions.', 'admin'),
('roles.manage', 'Manage Roles', 'Allows creating and updating roles, including role permission assignments.', 'admin'),
('roles.delete', 'Delete Roles', 'Allows permanently deleting roles.', 'admin'),
('permissions.view', 'View Permissions', 'Allows viewing the full permission catalog and metadata.', 'admin'),
('permissions.manage', 'Manage Permissions', 'Allows creating and maintaining permission definitions.', 'admin'),
('users.view', 'View Users', 'Allows viewing users, account status, and assigned roles.', 'admin'),
('users.manage', 'Manage Users', 'Allows creating users, updating role assignments, activating/deactivating users, and resetting passwords.', 'admin'),
('users.delete', 'Delete Users', 'Allows permanently deleting user accounts.', 'admin'),
('feedback.create', 'Submit Feedback', 'Allows submitting feedback via text, audio upload, or microphone recording.', 'submit'),
('feedback.read_own', 'View Own Feedback', 'Allows viewing feedback created by the logged-in user.', 'my_feedback'),
('feedback.read_all', 'View All Feedback', 'Allows viewing all feedback records across the system.', 'feedback_board'),
('feedback.read_assigned', 'View Assigned Feedback Only', 'Allows viewing only feedback items assigned to the logged-in user.', 'feedback_board'),
('feedback.update', 'Update Feedback Status', 'Allows updating workflow fields such as status and priority.', 'feedback_board'),
('feedback.assign', 'Assign Feedback Owner', 'Allows assigning/reassigning feedback items to other users.', 'feedback_board'),
('feedback.analysis.view', 'View Analysis Details', 'Allows opening analysis panels and viewing AI analysis details.', 'feedback_board'),
('feedback.transcript.original.view', 'View Original Transcript', 'Allows viewing original transcript text, subject to masking policy.', 'feedback_board'),
('feedback.sensitive.view', 'View Sensitive Content', 'Legacy visibility flag for sensitive fields. Masking behavior is primarily controlled by feedback.sensitive.mask.', 'feedback_board'),
('feedback.sensitive.mask', 'Mask Sensitive Content', 'When enabled for a role, sensitive content is redacted in message/transcript/analysis fields.', 'feedback_board'),
('feedback.submitter.view', 'View Submitter Name', 'Shows who submitted each feedback item (e.g. beside the timestamp on the feedback board).', 'feedback_board'),
('dashboard.view', 'View Dashboard', 'Allows opening dashboard tab and viewing dashboard metrics.', 'dashboard'),
('ai.cost.view', 'View AI Cost Metrics', 'Allows viewing Whisper/GPT/total AI processing cost metrics.', 'dashboard')
ON CONFLICT (key) DO UPDATE SET
  label = EXCLUDED.label,
  description = EXCLUDED.description,
  tab_key = EXCLUDED.tab_key;

-- 2) Ensure superadmin always has all permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON 1=1
WHERE r.name = 'superadmin'
ON CONFLICT DO NOTHING;

-- 3) Ensure known default grants remain present for admin/resolver/tracker/student
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key IN (
  'users.view', 'users.delete',
  'roles.delete',
  'feedback.read_all', 'feedback.update',
  'feedback.analysis.view', 'feedback.transcript.original.view', 'feedback.sensitive.view',
  'feedback.submitter.view',
  'dashboard.view', 'ai.cost.view'
)
WHERE r.name = 'admin'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key IN ('feedback.create', 'feedback.read_own', 'dashboard.view', 'feedback.sensitive.mask')
WHERE r.name = 'student'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key IN ('feedback.read_assigned', 'feedback.update', 'feedback.analysis.view', 'feedback.submitter.view', 'dashboard.view', 'feedback.sensitive.mask')
WHERE r.name = 'resolver'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key IN (
  'feedback.read_all', 'feedback.assign',
  'feedback.analysis.view', 'feedback.transcript.original.view', 'feedback.sensitive.view',
  'feedback.submitter.view',
  'dashboard.view', 'ai.cost.view', 'feedback.sensitive.mask'
)
WHERE r.name = 'tracker'
ON CONFLICT DO NOTHING;
