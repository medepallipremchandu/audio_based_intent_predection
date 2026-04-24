-- Permission-gated tab: live demo fetch of public Reddit / Bluesky posts (preview + optional import).

INSERT INTO permissions (key, label, description, tab_key)
VALUES (
    'social_feed.demo',
    'Social feed demo (Reddit / Bluesky)',
    'Allows opening the Social feed tab, previewing public posts from configured sources, and importing selected rows as feedback (requires Submit Feedback for import).',
    'social_feed'
)
ON CONFLICT (key) DO UPDATE SET
  label = EXCLUDED.label,
  description = EXCLUDED.description,
  tab_key = EXCLUDED.tab_key;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key = 'social_feed.demo'
WHERE r.name = 'superadmin'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key = 'social_feed.demo'
WHERE r.name = 'admin'
ON CONFLICT DO NOTHING;
