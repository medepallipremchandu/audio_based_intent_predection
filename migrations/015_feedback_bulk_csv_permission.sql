-- Bulk CSV upload on Submit tab: requires Submit Feedback + this permission.

INSERT INTO permissions (key, label, description, tab_key)
VALUES (
    'feedback.bulk_csv',
    'Bulk CSV upload',
    'Allows uploading a CSV file on the Submit tab to create multiple text feedback rows (max 500 per file). Requires Submit Feedback.',
    'submit'
)
ON CONFLICT (key) DO UPDATE SET
  label = EXCLUDED.label,
  description = EXCLUDED.description,
  tab_key = EXCLUDED.tab_key;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key = 'feedback.bulk_csv'
WHERE r.name = 'superadmin'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key = 'feedback.bulk_csv'
WHERE r.name = 'admin'
ON CONFLICT DO NOTHING;
