ALTER TABLE feedbacks ADD COLUMN IF NOT EXISTS original_message TEXT;
ALTER TABLE feedbacks ADD COLUMN IF NOT EXISTS analysis_json TEXT;

INSERT INTO permissions (key, label, tab_key) VALUES
('feedback.analysis.view', 'View feedback analysis details', 'feedback_board'),
('feedback.transcript.original.view', 'View original transcript', 'feedback_board'),
('feedback.sensitive.view', 'View sensitive text', 'feedback_board')
ON CONFLICT (key) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key IN ('feedback.analysis.view', 'feedback.transcript.original.view', 'feedback.sensitive.view')
WHERE r.name IN ('superadmin', 'admin', 'tracker')
ON CONFLICT DO NOTHING;
