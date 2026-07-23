import re

with open("frontend/src/components/entities/EntityForm.tsx", "r") as f:
    content = f.read()

# Fix EntityForm state initialization
init_str = """  const [formData, setFormData] = useState({
    name: '',
    type: 'PERSON' as EntityType,
    confidence: 0.8,
    metadata: {
      description: '',
      aliases: [] as string[],
      category: '',
      properties: {} as Record<string, any>
    }
  });

  const [metadataFields, setMetadataFields] = useState<MetadataField[]>([]);"""

new_init_str = """  const [formData, setFormData] = useState(() => {
    if (entity) {
      return {
        name: entity.name || '',
        type: (entity.type || 'PERSON') as EntityType,
        confidence: entity.confidence || 0.8,
        metadata: {
          description: entity.metadata?.description || '',
          aliases: entity.metadata?.aliases || [],
          category: entity.metadata?.category || '',
          properties: entity.metadata?.properties || {}
        }
      };
    }
    return {
      name: '',
      type: 'PERSON' as EntityType,
      confidence: 0.8,
      metadata: {
        description: '',
        aliases: [] as string[],
        category: '',
        properties: {} as Record<string, any>
      }
    };
  });

  const [metadataFields, setMetadataFields] = useState<MetadataField[]>(() => {
    if (entity && entity.metadata?.properties) {
      return Object.entries(entity.metadata.properties).map(([key, value]) => {
        let type: MetadataField['type'] = 'string';
        if (typeof value === 'number') type = 'number';
        else if (typeof value === 'boolean') type = 'boolean';
        else if (Array.isArray(value)) type = 'array';
        else if (typeof value === 'object') type = 'object';

        return {
          key,
          value: typeof value === 'object' ? JSON.stringify(value) : String(value),
          type
        };
      });
    }
    return [];
  });"""

content = content.replace(init_str, new_init_str)

effect_str = """  useEffect(() => {
    if (entity) {
      setFormData({
        name: entity.name || '',
        type: entity.type || 'PERSON',
        confidence: entity.confidence || 0.8,
        metadata: {
          description: entity.metadata?.description || '',
          aliases: entity.metadata?.aliases || [],
          category: entity.metadata?.category || '',
          properties: entity.metadata?.properties || {}
        }
      });

      // Convert metadata object back to fields array
      if (entity.metadata?.properties) {
        const fields: MetadataField[] = Object.entries(entity.metadata.properties).map(([key, value]) => {
          let type: MetadataField['type'] = 'string';
          if (typeof value === 'number') type = 'number';
          else if (typeof value === 'boolean') type = 'boolean';
          else if (Array.isArray(value)) type = 'array';
          else if (typeof value === 'object') type = 'object';

          return {
            key,
            value: typeof value === 'object' ? JSON.stringify(value) : String(value),
            type
          };
        });
        setMetadataFields(fields);
      }
    }
  }, [entity]);"""

content = content.replace(effect_str, "  // Removed useEffect setting state to avoid cascading renders. State initialized above.")

with open("frontend/src/components/entities/EntityForm.tsx", "w") as f:
    f.write(content)


with open("frontend/src/components/entities/RelationshipForm.tsx", "r") as f:
    content_rel = f.read()

init_rel_str = """  const [formData, setFormData] = useState({
    source_entity_id: sourceEntityId || '',
    target_entity_id: '',
    relationship_type: '',
    strength: 0.8,
    confidence_score: 0.8,
    context: '',
    evidence: [] as string[],
    metadata: {} as Record<string, any>
  });"""

new_init_rel_str = """  const [formData, setFormData] = useState(() => {
    if (initialData) {
      return {
        source_entity_id: initialData.source || sourceEntityId || '',
        target_entity_id: initialData.target || '',
        relationship_type: initialData.type || '',
        strength: initialData.weight || 0.8,
        confidence_score: initialData.confidence || 0.8,
        context: initialData.context || '',
        evidence: initialData.evidence || [],
        metadata: initialData.metadata || {}
      };
    }
    return {
      source_entity_id: sourceEntityId || '',
      target_entity_id: '',
      relationship_type: '',
      strength: 0.8,
      confidence_score: 0.8,
      context: '',
      evidence: [] as string[],
      metadata: {} as Record<string, any>
    };
  });"""

content_rel = content_rel.replace(init_rel_str, new_init_rel_str)

effect_rel_str = """  useEffect(() => {
    if (initialData) {
      setFormData({
        source_entity_id: initialData.source || '',
        target_entity_id: initialData.target || '',
        relationship_type: initialData.type || '',
        strength: initialData.weight || 0.8,
        confidence_score: initialData.confidence || 0.8,
        context: initialData.context || '',
        evidence: initialData.evidence || [],
        metadata: initialData.metadata || {}
      });
    }
  }, [initialData]);"""

content_rel = content_rel.replace(effect_rel_str, "  // Removed useEffect setting state to avoid cascading renders. State initialized above.")

with open("frontend/src/components/entities/RelationshipForm.tsx", "w") as f:
    f.write(content_rel)

print("done")
