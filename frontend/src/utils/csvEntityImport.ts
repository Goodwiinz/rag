import Papa from 'papaparse';

export interface BulkCsvEntityInput {
  name: string;
  entity_type: string;
  confidence_score: number;
  extraction_method: string;
  metadata: Record<string, never>;
}

const FORMULA_PREFIX_PATTERN = /^[=+\-@]+/;

export function sanitizeCsvCell(value: string | undefined): string {
  if (!value) {
    return '';
  }

  const normalized = value.trim();
  if (!normalized) {
    return '';
  }

  return normalized.replace(FORMULA_PREFIX_PATTERN, '');
}

export function parseBulkEntitiesFromCsv(csvInput: string): BulkCsvEntityInput[] {
  const parsed = Papa.parse<Record<string, string>>(csvInput, {
    header: true,
    skipEmptyLines: 'greedy',
    transformHeader: (header) => header.trim().toLowerCase(),
    transform: (value) => value.trim(),
  });

  if (parsed.errors.length > 0) {
    const firstError = parsed.errors[0];
    const lineNumber =
      typeof firstError.row === 'number' ? firstError.row + 2 : 'unknown';
    throw new Error(`CSV parsing error on line ${lineNumber}: ${firstError.message}`);
  }

  const entities: BulkCsvEntityInput[] = [];
  const missingNameRows: number[] = [];

  parsed.data.forEach((row, index) => {
    const rowNumber = index + 2;
    const name = sanitizeCsvCell(row.name);

    if (!name) {
      missingNameRows.push(rowNumber);
      return;
    }

    const confidence = Number.parseFloat(row.confidence_score ?? '0.8');

    entities.push({
      name,
      entity_type: sanitizeCsvCell(row.entity_type ?? row.type),
      confidence_score: Number.isFinite(confidence) ? confidence : 0.8,
      extraction_method: sanitizeCsvCell(row.extraction_method) || 'manual',
      metadata: {},
    });
  });

  if (missingNameRows.length > 0) {
    throw new Error(`CSV rows missing required "name": ${missingNameRows.join(', ')}`);
  }

  if (entities.length === 0) {
    throw new Error('CSV must have at least one valid data row');
  }

  return entities;
}
