-- Permission to download stored feedback audio (separate from in-app playback).

INSERT INTO permissions (key, label, description, tab_key)
VALUES
(
  'feedback.audio.download',
  'Download Original Audio',
  'Allows downloading the stored audio file from the Audio Signal tab. Playback in the app does not require this permission.',
  'feedback_board'
)
ON CONFLICT (key) DO UPDATE SET
  label = EXCLUDED.label,
  description = EXCLUDED.description,
  tab_key = EXCLUDED.tab_key;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key = 'feedback.audio.download'
WHERE r.name = 'superadmin'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key = 'feedback.audio.download'
WHERE r.name IN ('admin', 'tracker', 'resolver', 'student')
ON CONFLICT DO NOTHING;
