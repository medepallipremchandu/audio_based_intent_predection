-- Who submitted this feedback (name next to timestamp) — permission-gated in API + UI.

INSERT INTO permissions (key, label, description, tab_key)
VALUES (
  'feedback.submitter.view',
  'View Submitter Name',
  'Shows the display name of the user who submitted each feedback item (e.g. beside the date on the feedback board).',
  'feedback_board'
)
ON CONFLICT (key) DO UPDATE SET
  label = EXCLUDED.label,
  description = EXCLUDED.description,
  tab_key = EXCLUDED.tab_key;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.key = 'feedback.submitter.view'
WHERE r.name IN ('superadmin', 'admin', 'tracker', 'resolver')
ON CONFLICT DO NOTHING;
