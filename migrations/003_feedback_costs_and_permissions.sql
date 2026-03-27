ALTER TABLE feedbacks ADD COLUMN IF NOT EXISTS input_type VARCHAR(20) NOT NULL DEFAULT 'text';
ALTER TABLE feedbacks ADD COLUMN IF NOT EXISTS whisper_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0;
ALTER TABLE feedbacks ADD COLUMN IF NOT EXISTS gpt_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0;
ALTER TABLE feedbacks ADD COLUMN IF NOT EXISTS total_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0;

INSERT INTO permissions (key, label, tab_key)
VALUES
('ai.cost.view', 'View AI and Whisper cost', 'dashboard')
ON CONFLICT (key) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key = 'ai.cost.view'
WHERE r.name IN ('superadmin', 'admin', 'tracker')
ON CONFLICT DO NOTHING;
