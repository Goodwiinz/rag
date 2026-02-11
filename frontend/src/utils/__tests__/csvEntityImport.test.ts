import {
  parseBulkEntitiesFromCsv,
  sanitizeCsvCell,
} from '../csvEntityImport';

describe('csvEntityImport', () => {
  it('parses quoted CSV fields with commas', () => {
    const csv = [
      'name,entity_type,confidence_score,extraction_method',
      '"Smith, John",PERSON,0.9,manual',
    ].join('\n');

    const entities = parseBulkEntitiesFromCsv(csv);

    expect(entities).toHaveLength(1);
    expect(entities[0].name).toBe('Smith, John');
    expect(entities[0].entity_type).toBe('PERSON');
    expect(entities[0].confidence_score).toBe(0.9);
    expect(entities[0].extraction_method).toBe('manual');
  });

  it('sanitizes formula-leading characters to reduce CSV injection risk', () => {
    const csv = [
      'name,entity_type,confidence_score,extraction_method',
      '=HYPERLINK("http://bad"),@PERSON,0.7,+manual',
    ].join('\n');

    const entities = parseBulkEntitiesFromCsv(csv);

    expect(entities).toHaveLength(1);
    expect(entities[0].name).toBe('HYPERLINK("http://bad")');
    expect(entities[0].entity_type).toBe('PERSON');
    expect(entities[0].extraction_method).toBe('manual');
  });

  it('removes repeated formula-leading characters', () => {
    const csv = [
      'name,entity_type,confidence_score,extraction_method',
      '==2+2,@@PERSON,0.7,++manual',
    ].join('\n');

    const entities = parseBulkEntitiesFromCsv(csv);

    expect(entities).toHaveLength(1);
    expect(entities[0].name).toBe('2+2');
    expect(entities[0].entity_type).toBe('PERSON');
    expect(entities[0].extraction_method).toBe('manual');
  });

  it('defaults confidence score to 0.8 for invalid values', () => {
    const csv = [
      'name,entity_type,confidence_score,extraction_method',
      'Entity One,CONCEPT,not-a-number,manual',
    ].join('\n');

    const entities = parseBulkEntitiesFromCsv(csv);

    expect(entities[0].confidence_score).toBe(0.8);
  });

  it('throws when a row is missing required name', () => {
    const csv = [
      'name,entity_type,confidence_score,extraction_method',
      ',CONCEPT,0.8,manual',
    ].join('\n');

    expect(() => parseBulkEntitiesFromCsv(csv)).toThrow(
      'CSV rows missing required "name"'
    );
  });

  it('trims values and strips dangerous prefixes from cells', () => {
    expect(sanitizeCsvCell('  +value ')).toBe('value');
    expect(sanitizeCsvCell('  safe  ')).toBe('safe');
    expect(sanitizeCsvCell(undefined)).toBe('');
  });
});
