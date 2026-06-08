import asyncio
from app.db.database import init_db, async_session_maker
from app.models.models import Organization, User, DocumentType, PromptVersion
from app.core.security import get_password_hash
from loguru import logger
from sqlalchemy import select

async def seed_data() -> None:
    logger.info("Initializing database schemas...")
    await init_db()
    
    async with async_session_maker() as session:
        # Check if organization exists
        stmt = select(Organization).where(Organization.name == "Acme Corp")
        result = await session.execute(stmt)
        org = result.scalar_one_or_none()
        
        if not org:
            logger.info("Seeding default organization 'Acme Corp'...")
            org = Organization(name="Acme Corp")
            session.add(org)
            await session.commit()
            await session.refresh(org)
            logger.info(f"Seeded Organization with ID: {org.id}")
        else:
            logger.info("Organization 'Acme Corp' already exists.")

        # Check if users exist
        users_to_seed = [
            ("admin@acme.com", "admin123", "admin"),
            ("reviewer@acme.com", "reviewer123", "reviewer"),
            ("user@acme.com", "user123", "user")
        ]
        
        for email, password, role in users_to_seed:
            stmt = select(User).where(User.email == email)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            
            if not user:
                logger.info(f"Seeding user: {email} ({role})...")
                user = User(
                    organization_id=org.id,
                    email=email,
                    hashed_password=get_password_hash(password),
                    role=role,
                    is_active=True
                )
                session.add(user)
                logger.info(f"Seeded User: {email}")
            else:
                logger.info(f"User {email} already exists.")
        
        await session.commit()

        # Seed Document Types
        doc_types = [
            {
                "name": "Invoice",
                "description": "Commercial invoice document for payments",
                "schema_definition": {
                    "fields": [
                        {"name": "invoice_number", "type": "string", "required": True, "description": "The unique invoice number identifier"},
                        {"name": "invoice_date", "type": "string", "required": True, "description": "Date of the invoice"},
                        {"name": "vendor_name", "type": "string", "required": True, "description": "Name of the merchant/vendor"},
                        {"name": "amount", "type": "number", "required": True, "description": "Total amount due"}
                    ]
                }
            },
            {
                "name": "Receipt",
                "description": "Sales or transaction receipt",
                "schema_definition": {
                    "fields": [
                        {"name": "receipt_number", "type": "string", "required": False, "description": "Unique transaction number"},
                        {"name": "date", "type": "string", "required": True, "description": "Transaction date"},
                        {"name": "vendor_name", "type": "string", "required": True, "description": "Vendor or merchant name"},
                        {"name": "total_amount", "type": "number", "required": True, "description": "Total amount paid"}
                    ]
                }
            },
            {
                "name": "Bank Statement",
                "description": "Periodic statement of a bank account",
                "schema_definition": {
                    "fields": [
                        {"name": "account_number", "type": "string", "required": True, "description": "Last 4 digits or full bank account number"},
                        {"name": "statement_date", "type": "string", "required": True, "description": "Ending date of the statement period"},
                        {"name": "starting_balance", "type": "number", "required": True, "description": "Starting balance of statement"},
                        {"name": "ending_balance", "type": "number", "required": True, "description": "Ending balance of statement"}
                    ]
                }
            },
            {
                "name": "Contract",
                "description": "Legal agreement between parties",
                "schema_definition": {
                    "fields": [
                        {"name": "contract_id", "type": "string", "required": False, "description": "Unique contract reference number"},
                        {"name": "parties", "type": "string", "required": True, "description": "Comma separated list of entities involved"},
                        {"name": "effective_date", "type": "string", "required": True, "description": "Date contract becomes active"},
                        {"name": "expiration_date", "type": "string", "required": False, "description": "Date contract expires"},
                        {"name": "total_value", "type": "number", "required": False, "description": "Total financial value of the contract"}
                    ]
                }
            },
            {
                "name": "Purchase Order",
                "description": "Standard business purchase order",
                "schema_definition": {
                    "fields": [
                        {"name": "po_number", "type": "string", "required": True, "description": "Unique purchase order number"},
                        {"name": "po_date", "type": "string", "required": True, "description": "Date the PO was generated"},
                        {"name": "vendor_name", "type": "string", "required": True, "description": "Vendor supplying the items"},
                        {"name": "total_amount", "type": "number", "required": True, "description": "Total purchase order amount"}
                    ]
                }
            }
        ]

        for dt in doc_types:
            stmt = select(DocumentType).where(DocumentType.name == dt["name"])
            res = await session.execute(stmt)
            exists = res.scalar_one_or_none()
            if not exists:
                logger.info(f"Seeding DocumentType: {dt['name']}...")
                doc_type = DocumentType(
                    organization_id=org.id,
                    name=dt["name"],
                    description=dt["description"],
                    schema_definition=dt["schema_definition"]
                )
                session.add(doc_type)
            else:
                logger.info(f"DocumentType {dt['name']} already exists.")
        
        # Seed default prompts
        prompts = [
            {
                "agent_name": "classification_agent",
                "version": 1,
                "system_prompt": "You are an AI document classifier. Analyze the provided document text and classify it into one of these types: Invoice, Receipt, Bank Statement, Contract, Purchase Order. Return ONLY a JSON block with the single key 'document_type'. Do not include extra text.",
                "user_prompt_template": "Document Text:\n{text}"
            },
            {
                "agent_name": "extraction_agent",
                "version": 1,
                "system_prompt": "You are a precise data extraction agent. Extract structured information from the document text based on the provided JSON Schema fields. Return a JSON block containing ONLY the extracted keys and values. Return null or omit fields not found in the text. Make sure values align with expected types (number, string, etc.).",
                "user_prompt_template": "Document Schema:\n{schema}\n\nDocument Text:\n{text}"
            },
            {
                "agent_name": "confidence_agent",
                "version": 1,
                "system_prompt": "You are an AI confidence scorer. Evaluate the accuracy of the extracted data against the original document text. Calculate a score between 0.00 and 1.00 indicating your confidence in the extraction quality. Provide a detailed rationale for your score. Return ONLY JSON with keys 'confidence_score' (float) and 'rationale' (string).",
                "user_prompt_template": "Original Text:\n{text}\n\nExtracted Data:\n{data}"
            }
        ]
        
        for pr in prompts:
            stmt = select(PromptVersion).where(
                PromptVersion.agent_name == pr["agent_name"],
                PromptVersion.version == pr["version"]
            )
            res = await session.execute(stmt)
            exists = res.scalar_one_or_none()
            if not exists:
                logger.info(f"Seeding PromptVersion: {pr['agent_name']} (v{pr['version']})...")
                p_ver = PromptVersion(
                    agent_name=pr["agent_name"],
                    version=pr["version"],
                    system_prompt=pr["system_prompt"],
                    user_prompt_template=pr["user_prompt_template"],
                    is_active=True
                )
                session.add(p_ver)
        
        await session.commit()
        logger.info("Database seeding completed successfully.")

if __name__ == "__main__":
    asyncio.run(seed_data())
