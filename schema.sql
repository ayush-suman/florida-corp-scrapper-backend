CREATE TABLE IF NOT EXISTS entity_details (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(100),
    entity_name VARCHAR(255),
    document_number VARCHAR(50),
    fe_ein_number VARCHAR(50),
    date_filed DATE,
    effective_date DATE,
    state VARCHAR(10),
    status VARCHAR(50),
    principal_address TEXT,
    principal_address_changed DATE,
    mailing_address TEXT,
    mailing_address_changed DATE,
    registered_agent_name VARCHAR(255),
    registered_agent_address TEXT,
    registered_agent_address_changed DATE,

    authorized_persons JSONB,
    annual_reports JSONB,
    document_images JSONB,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
