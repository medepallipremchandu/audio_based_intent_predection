CREATE TABLE IF NOT EXISTS feedback_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

ALTER TABLE feedbacks ADD COLUMN IF NOT EXISTS source_id INTEGER REFERENCES feedback_sources(id) ON DELETE SET NULL;
ALTER TABLE feedbacks ADD COLUMN IF NOT EXISTS department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL;
ALTER TABLE feedbacks ADD COLUMN IF NOT EXISTS course_code VARCHAR(80);

INSERT INTO feedback_sources (name, is_active) VALUES
('Course Survey', TRUE),
('Exit Poll', TRUE),
('Anonymous Submission', TRUE),
('End-of-Term Review', TRUE),
('Department Forum', TRUE)
ON CONFLICT (name) DO NOTHING;

INSERT INTO departments (name, is_active) VALUES
('Not specified', TRUE),
('Computer Science', TRUE),
('Business Administration', TRUE),
('Engineering', TRUE),
('Arts & Humanities', TRUE),
('Natural Sciences', TRUE),
('Social Sciences', TRUE),
('Health Sciences', TRUE)
ON CONFLICT (name) DO NOTHING;
