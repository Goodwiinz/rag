#!/usr/bin/env python3
"""
Script to re-classify OTHER entities using Azure OpenAI LLM.
This fixes legacy entities that were incorrectly classified as OTHER.

Estimated cost: ~$0.01 per 50 entities (batch classification)
For 797 entities: ~$0.16
"""

import asyncio
import logging
import os
import sys
import json
from typing import List, Dict, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("reclassify_entities")

# Entity types we want to classify into
ENTITY_TYPES = [
    "METHODOLOGY",      # Research methods, techniques, algorithms
    "MODEL",            # ML/AI models (GPT, BERT, ResNet, etc.)
    "METRIC",           # Evaluation metrics (accuracy, F1, BLEU, etc.)
    "TASK",             # Research tasks (classification, detection, etc.)
    "DATASET",          # Datasets (ImageNet, COCO, nuScenes, etc.)
    "FRAMEWORK",        # Software frameworks (PyTorch, TensorFlow, etc.)
    "THEORY",           # Theoretical concepts, mathematical theories
    "DOMAIN",           # Application domains (NLP, CV, robotics, etc.)
    "ARCHITECTURE",     # Model architectures (Transformer, CNN, etc.)
    "LOSS_FUNCTION",    # Loss functions (cross-entropy, MSE, etc.)
    "OPTIMIZATION",     # Optimization methods (Adam, SGD, etc.)
    "INSTITUTION",      # Universities, companies, research labs
    "BENCHMARK",        # Benchmark suites or challenges
]

CLASSIFICATION_PROMPT = """You are an expert at classifying research entities from academic papers.

Given a list of entity names, classify each one into exactly ONE of these types:
- METHODOLOGY: Research methods, techniques, algorithms, approaches
- MODEL: Specific ML/AI models (GPT-4, BERT, ResNet-50, LLaMA, etc.)
- METRIC: Evaluation metrics (accuracy, F1-score, BLEU, perplexity, etc.)
- TASK: Research tasks (image classification, object detection, translation, etc.)
- DATASET: Named datasets (ImageNet, COCO, nuScenes, KITTI, etc.)
- FRAMEWORK: Software frameworks and libraries (PyTorch, TensorFlow, Hugging Face, etc.)
- THEORY: Theoretical concepts, mathematical principles
- DOMAIN: Application domains or fields (computer vision, NLP, robotics, etc.)
- ARCHITECTURE: Model architectures or components (Transformer, CNN, attention mechanism, etc.)
- LOSS_FUNCTION: Loss/objective functions (cross-entropy, MSE, contrastive loss, etc.)
- OPTIMIZATION: Optimization algorithms (Adam, SGD, learning rate scheduling, etc.)
- INSTITUTION: Universities, companies, research labs
- BENCHMARK: Benchmark suites or evaluation challenges
- SKIP: If the entity is too generic, meaningless, or cannot be classified

Respond with a JSON array where each object has "name" and "type" fields.

Entities to classify:
{entities}

JSON response:"""


async def get_other_entities(driver) -> List[Dict]:
    """Get all entities with OTHER label or NULL type."""
    async with driver.session() as session:
        # Get entities with :OTHER label
        result = await session.run("""
            MATCH (e:OTHER)
            RETURN e.name AS name, id(e) AS node_id, labels(e) AS labels
            UNION
            MATCH (e:Entity)
            WHERE e.type IS NULL OR e.type = 'OTHER'
            RETURN e.name AS name, id(e) AS node_id, labels(e) AS labels
        """)
        entities = [
            {"name": r["name"], "node_id": r["node_id"], "labels": r["labels"]}
            async for r in result
        ]
        return entities


async def classify_entities_batch(client, entities: List[str], deployment_name: str) -> Dict[str, str]:
    """Classify a batch of entities using Azure OpenAI."""
    from openai import AzureOpenAI

    entities_str = "\n".join(f"- {e}" for e in entities)

    response = client.chat.completions.create(
        model=deployment_name,
        messages=[
            {"role": "system", "content": "You are an expert at classifying research entities. Always respond with valid JSON."},
            {"role": "user", "content": CLASSIFICATION_PROMPT.format(entities=entities_str)}
        ],
        temperature=0.1,
        max_tokens=2000
    )

    content = response.choices[0].message.content.strip()

    # Parse JSON response
    try:
        # Handle markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        classifications = json.loads(content)
        return {item["name"]: item["type"] for item in classifications}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        logger.error(f"Response: {content}")
        return {}


async def update_entity_type(driver, node_id: int, old_labels: List[str], new_type: str):
    """Update an entity's type in Neo4j."""
    async with driver.session() as session:
        # Remove :OTHER label if present and add new type label
        # Also set the type property
        await session.run(f"""
            MATCH (e) WHERE id(e) = $node_id
            REMOVE e:OTHER
            SET e:{new_type}, e.type = $new_type
        """, {"node_id": node_id, "new_type": new_type})


async def run_reclassification(batch_size: int = 50, dry_run: bool = False):
    """Main function to reclassify OTHER entities."""
    from neo4j import AsyncGraphDatabase
    from openai import AzureOpenAI

    # Initialize connections
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

    driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_CHAT_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_CHAT_API_VERSION", "2024-06-01"),
        azure_endpoint=os.getenv("AZURE_OPENAI_CHAT_ENDPOINT")
    )

    deployment_name = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4o-mini")
    logger.info(f"Using Azure OpenAI deployment: {deployment_name}")

    try:
        # Get all OTHER entities
        logger.info("Fetching OTHER entities from Neo4j...")
        entities = await get_other_entities(driver)
        logger.info(f"Found {len(entities)} entities to reclassify")

        if not entities:
            logger.info("No entities to reclassify!")
            return

        # Process in batches
        total_updated = 0
        total_skipped = 0
        type_counts = {}

        for i in range(0, len(entities), batch_size):
            batch = entities[i:i + batch_size]
            batch_names = [e["name"] for e in batch if e["name"]]

            logger.info(f"Processing batch {i // batch_size + 1}/{(len(entities) + batch_size - 1) // batch_size}")

            # Classify batch
            classifications = await classify_entities_batch(client, batch_names, deployment_name)

            # Update entities
            for entity in batch:
                name = entity["name"]
                if not name or name not in classifications:
                    continue

                new_type = classifications[name]

                if new_type == "SKIP":
                    total_skipped += 1
                    continue

                if new_type not in ENTITY_TYPES:
                    logger.warning(f"Unknown type '{new_type}' for entity '{name}', skipping")
                    total_skipped += 1
                    continue

                type_counts[new_type] = type_counts.get(new_type, 0) + 1

                if not dry_run:
                    await update_entity_type(
                        driver,
                        entity["node_id"],
                        entity["labels"],
                        new_type
                    )
                    total_updated += 1
                else:
                    logger.info(f"  [DRY RUN] Would update '{name}' → {new_type}")
                    total_updated += 1

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)

        # Summary
        logger.info("")
        logger.info("=" * 50)
        logger.info("RECLASSIFICATION COMPLETE")
        logger.info("=" * 50)
        logger.info(f"Total entities processed: {len(entities)}")
        logger.info(f"Total updated: {total_updated}")
        logger.info(f"Total skipped: {total_skipped}")
        logger.info("")
        logger.info("Type distribution:")
        for entity_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            logger.info(f"  {entity_type}: {count}")

        if dry_run:
            logger.info("")
            logger.info("This was a DRY RUN. No changes were made.")
            logger.info("Run with --execute to apply changes.")

    finally:
        await driver.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Reclassify OTHER entities using LLM")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for LLM classification")
    parser.add_argument("--execute", action="store_true", help="Actually apply changes (default is dry run)")

    args = parser.parse_args()

    dry_run = not args.execute

    if dry_run:
        logger.info("Running in DRY RUN mode. Use --execute to apply changes.")
    else:
        logger.info("Running in EXECUTE mode. Changes will be applied to Neo4j.")

    asyncio.run(run_reclassification(batch_size=args.batch_size, dry_run=dry_run))
