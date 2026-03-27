ALTER TABLE permissions ADD COLUMN IF NOT EXISTS description TEXT;

UPDATE permissions SET
  label = 'Full System Access',
  description = 'Grants unrestricted access to all features, routes, and admin controls. Intended only for super administrators.'
WHERE key = 'system.superadmin';

UPDATE permissions SET
  label = 'View Roles',
  description = 'Allows viewing role list, role names, role descriptions, and assigned permissions.'
WHERE key = 'roles.view';

UPDATE permissions SET
  label = 'Manage Roles',
  description = 'Allows creating new roles and updating role details including permission assignments.'
WHERE key = 'roles.manage';

UPDATE permissions SET
  label = 'Delete Roles',
  description = 'Allows permanently deleting roles. Use carefully because users assigned to this role will lose these permissions.'
WHERE key = 'roles.delete';

UPDATE permissions SET
  label = 'View Permissions',
  description = 'Allows viewing all permission keys, labels, descriptions, and tab mappings.'
WHERE key = 'permissions.view';

UPDATE permissions SET
  label = 'Manage Permissions',
  description = 'Allows creating new permissions and maintaining permission metadata.'
WHERE key = 'permissions.manage';

UPDATE permissions SET
  label = 'View Users',
  description = 'Allows viewing user profiles, account status, and role assignments.'
WHERE key = 'users.view';

UPDATE permissions SET
  label = 'Manage Users',
  description = 'Allows creating users, updating user roles, activating/deactivating users, and resetting passwords.'
WHERE key = 'users.manage';

UPDATE permissions SET
  label = 'Delete Users',
  description = 'Allows permanently deleting user accounts. This action removes login access and related role mappings.'
WHERE key = 'users.delete';

UPDATE permissions SET
  label = 'Submit Feedback',
  description = 'Allows submitting new feedback entries through text input, audio upload, or microphone recording.'
WHERE key = 'feedback.create';

UPDATE permissions SET
  label = 'View Own Feedback',
  description = 'Allows viewing feedback records submitted by the currently logged-in user only.'
WHERE key = 'feedback.read_own';

UPDATE permissions SET
  label = 'View All Feedback',
  description = 'Allows viewing all feedback records across all users in the feedback board.'
WHERE key = 'feedback.read_all';

UPDATE permissions SET
  label = 'View Assigned Feedback Only',
  description = 'Allows viewing only feedback items assigned to the logged-in user. Use this for resolver-style limited access.'
WHERE key = 'feedback.read_assigned';

UPDATE permissions SET
  label = 'Update Feedback Status',
  description = 'Allows changing workflow fields such as status (soon, in progress, completed) and priority.'
WHERE key = 'feedback.update';

UPDATE permissions SET
  label = 'Assign Feedback Owner',
  description = 'Allows assigning or reassigning feedback items to a resolver/tracker user.'
WHERE key = 'feedback.assign';

UPDATE permissions SET
  label = 'View Analysis Details',
  description = 'Allows opening analysis panels and viewing sentiment, intent, evidence, action items, and related AI insights.'
WHERE key = 'feedback.analysis.view';

UPDATE permissions SET
  label = 'View Original Transcript',
  description = 'Allows viewing the unmodified transcript text (subject to masking policy if sensitive masking is enabled for the role).'
WHERE key = 'feedback.transcript.original.view';

UPDATE permissions SET
  label = 'View Sensitive Content',
  description = 'Legacy sensitive-content visibility flag. In this project, sensitive masking behavior is primarily controlled by feedback.sensitive.mask.'
WHERE key = 'feedback.sensitive.view';

UPDATE permissions SET
  label = 'Mask Sensitive Content',
  description = 'When enabled for a role, sensitive values are redacted in feedback message, transcript, and analysis fields. When disabled, original content can be shown.'
WHERE key = 'feedback.sensitive.mask';

UPDATE permissions SET
  label = 'View Dashboard',
  description = 'Allows opening the dashboard tab and viewing dashboard KPIs/charts based on the user data scope.'
WHERE key = 'dashboard.view';

UPDATE permissions SET
  label = 'View AI Cost Metrics',
  description = 'Allows viewing Whisper, GPT, and total AI processing cost values on dashboard and feedback views.'
WHERE key = 'ai.cost.view';
