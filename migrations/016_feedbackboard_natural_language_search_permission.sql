-- Natural-language filter search on My Feedback.

INSERT INTO permissions (key, label, description, tab_key)
VALUES (
    'feedbackboard.naturallanguagesearch',
    'Natural Language Filter Search',
    'Allows using AI-powered natural language search in My Feedback to convert text queries into filter values.',
    'my_feedback'
)
ON CONFLICT (key) DO UPDATE SET
  label = EXCLUDED.label,
  description = EXCLUDED.description,
  tab_key = EXCLUDED.tab_key;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key = 'feedbackboard.naturallanguagesearch'
WHERE r.name = 'superadmin'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key = 'feedbackboard.naturallanguagesearch'
WHERE r.name = 'admin'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key = 'feedbackboard.naturallanguagesearch'
WHERE r.name = 'student'
ON CONFLICT DO NOTHING;
