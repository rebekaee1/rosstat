import { describe, expect, it } from 'vitest'
import cases from './uniformDigits.cases.json'
import { uniformDigits } from './countryFlag'

// Те же случаи читает backend/tests/test_world_value_digits.py: точность рейтинга мира одна у SPA и сервера.
describe('uniformDigits — общее правило точности рейтинга с сервером (14.11.2026)', () => {
  for (const item of cases.cases) {
    it(`${JSON.stringify(item.values)} → ${item.digits}`, () => {
      expect(uniformDigits(item.values)).toBe(item.digits)
    })
  }
})
