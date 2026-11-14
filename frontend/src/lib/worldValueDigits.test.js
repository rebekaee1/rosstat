import { describe, expect, it } from 'vitest'
import cases from './worldValueDigits.cases.json'
import { formatWorldValue, worldValueDigits } from './worldApi'

// Те же случаи читает backend/tests/test_world_value_digits.py: правило точности SPA и сервера одно.
const plain = (text) => text.replace(/[\u00A0\u202F]/g, ' ').replace(/\u2212/g, '-')

describe('worldValueDigits — общее правило точности с сервером (14.11.2026)', () => {
  for (const item of cases.cases) {
    it(`${item.values.join(', ')} → ${item.digits} знака`, () => {
      const digits = worldValueDigits(item.values)
      expect(digits).toBe(item.digits)
      expect(plain(formatWorldValue(item.values[0], digits, 'en'))).toBe(item.en)
      expect(plain(formatWorldValue(item.values[0], digits, 'ru'))).toBe(item.ru)
    })
  }
})
