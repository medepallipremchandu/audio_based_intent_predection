# Migration Notes

This folder keeps **append-only** SQL migrations. Earlier migrations are kept as-is for history.

## Current recommended understanding

- `001_init.sql`  
  Base schema (users, roles, permissions, feedbacks, mapping tables).

- `002_seed.sql`  
  Initial seed data (permissions, superadmin user, default role mappings).

- `003_feedback_costs_and_permissions.sql`  
  Feedback cost columns + `ai.cost.view` permission.

- `004_feedback_analysis_permissions.sql`  
  Feedback analysis columns + analysis-related permission grants.

- `005_analysis_permission_for_resolver.sql`  
  Resolver grant for analysis visibility.

- `006_feedback_lookup_tables.sql`  
  Source/department lookup tables + feedback form metadata columns.

- `007_feedback_audio_blob.sql`  
  Audio blob storage columns on feedback.

- `008_sensitive_mask_permission.sql`  
  Adds `feedback.sensitive.mask` and default masking grants.

- `009_permission_descriptions_and_clear_labels.sql`  
  Adds permission descriptions and improves labels/descriptions.

- `010_user_role_delete_permissions.sql`  
  Adds `users.delete` and `roles.delete` permissions.

- `011_permissions_reconciliation.sql`  
  Canonical reconciliation for permission labels/descriptions/tab mappings and key default grants.
  Use this as the single source of truth for permission meanings.

- `012_feedback_submitter_view_permission.sql`  
  Adds `feedback.submitter.view` (show submitter name beside timestamp on feedback cards).

- `013_feedback_audio_download_permission.sql`  
  Adds `feedback.audio.download` (download stored audio from the Audio Signal tab).

- `016_feedbackboard_natural_language_search_permission.sql`  
  Adds `feedbackboard.naturallanguagesearch` for AI-assisted natural language filter search in My Feedback.

## Why there are multiple permission migrations

Permissions evolved across features. To avoid breaking already-applied environments, this project keeps historical migrations and adds reconciliation migrations later (instead of rewriting old applied files).
