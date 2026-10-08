/** @vitest-environment jsdom */
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { LocaleProvider } from '../i18n';
import CalcMoneyField from './CalcMoneyField';
import CalcSlider from './CalcSlider';

afterEach(cleanup);

function Harness({ initial = 100000, onValue, locale, allowZero }) {
  const [value, setValue] = useState(initial);
  return (
    <LocaleProvider locale={locale}>
      <CalcMoneyField
        id="amt"
        label={locale === 'en' ? 'Amount' : 'Сумма'}
        unitName="в рублях"
        value={value}
        prefix="₽"
        allowZero={allowZero}
        onChange={(v) => { setValue(v); onValue?.(v); }}
      />
      <output data-testid="value">{value}</output>
    </LocaleProvider>
  );
}

describe('CalcMoneyField', () => {
  it('uses the decimal keyboard and a label tied to the input', () => {
    render(<Harness />);
    const input = screen.getByLabelText(/Сумма/);
    expect(input.getAttribute('inputmode')).toBe('decimal');
    expect(input.value).toBe('100 000');
    expect(input.getAttribute('aria-invalid')).toBeNull();
  });

  it('shows a visible message for letters and keeps the previous value instead of resetting it', () => {
    const onValue = vi.fn();
    render(<Harness onValue={onValue} />);
    const input = screen.getByLabelText(/Сумма/);
    fireEvent.change(input, { target: { value: '12ab' } });
    const alert = screen.getByRole('alert');
    expect(alert.textContent).toMatch(/только цифры/);
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(input.getAttribute('aria-describedby')).toBe(alert.id);
    expect(input.value).toBe('12ab');
    expect(onValue).not.toHaveBeenCalled();
    expect(screen.getByTestId('value').textContent).toBe('100000');
  });

  it('clears the message and passes the new value as soon as the input is valid', () => {
    const onValue = vi.fn();
    render(<Harness onValue={onValue} />);
    const input = screen.getByLabelText(/Сумма/);
    fireEvent.change(input, { target: { value: 'x' } });
    expect(screen.getByRole('alert')).toBeTruthy();
    fireEvent.change(input, { target: { value: '2500000' } });
    expect(screen.queryByRole('alert')).toBeNull();
    expect(onValue).toHaveBeenLastCalledWith(2500000);
    expect(input.value).toBe('2 500 000');
  });

  it('does not nag about an empty field while typing, but explains it on blur', () => {
    render(<Harness />);
    const input = screen.getByLabelText(/Сумма/);
    fireEvent.change(input, { target: { value: '' } });
    expect(screen.queryByRole('alert')).toBeNull();
    fireEvent.blur(input);
    expect(screen.getByRole('alert').textContent).toMatch(/больше нуля/);
    expect(screen.getByTestId('value').textContent).toBe('100000');
  });

  it('rejects an oversized amount and names the limit', () => {
    render(<Harness />);
    fireEvent.change(screen.getByLabelText(/Сумма/), { target: { value: '99999999999999' } });
    expect(screen.getByRole('alert').textContent).toMatch(/максимум 1.000.000.000.000/);
  });

  it('accepts zero when allowed (compound calculator contributions)', () => {
    render(<Harness allowZero />);
    fireEvent.change(screen.getByLabelText(/Сумма/), { target: { value: '0' } });
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByTestId('value').textContent).toBe('0');
  });

  it('speaks English in the EN storefront', () => {
    render(<Harness locale="en" />);
    fireEvent.change(screen.getByLabelText(/Amount/), { target: { value: 'abc' } });
    expect(screen.getByRole('alert').textContent).toMatch(/digits only/);
  });

  it('syncs the text when the parent changes the value from outside', () => {
    const { rerender } = render(
      <LocaleProvider>
        <CalcMoneyField id="a" label="Сумма" value={1000} onChange={() => {}} />
      </LocaleProvider>,
    );
    rerender(
      <LocaleProvider>
        <CalcMoneyField id="a" label="Сумма" value={250000} onChange={() => {}} />
      </LocaleProvider>,
    );
    expect(screen.getByLabelText('Сумма').value).toBe('250 000');
  });
});

describe('CalcSlider', () => {
  it('shows the value with its unit and exposes it to screen readers', () => {
    render(
      <LocaleProvider>
        <CalcSlider label="Ставка, % годовых" value={12.5} min={0.1} max={30} step={0.1} suffix="%" onChange={() => {}} />
        <CalcSlider label="Срок, лет" value={20} min={1} max={30} display="20 лет" onChange={() => {}} />
      </LocaleProvider>,
    );
    expect(screen.getByText('12,5%')).toBeTruthy();
    expect(screen.getByText('20 лет')).toBeTruthy();
    const rate = screen.getByLabelText('Ставка, % годовых');
    expect(rate.getAttribute('aria-valuetext')).toBe('12,5%');
    expect(screen.getByLabelText('Срок, лет').getAttribute('aria-valuetext')).toBe('20 лет');
  });

  it('keeps the dot decimal in English and reports numeric changes', () => {
    const onChange = vi.fn();
    render(
      <LocaleProvider locale="en">
        <CalcSlider label="Rate" value={12.5} min={0.1} max={30} step={0.1} suffix="%" onChange={onChange} />
      </LocaleProvider>,
    );
    expect(screen.getByText('12.5%')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Rate'), { target: { value: '14' } });
    expect(onChange).toHaveBeenCalledWith(14);
  });

  it('круг 9 (K5): число вводится рядом с бегунком; вне границ значение прижимается к ним', () => {
    const onChange = vi.fn();
    render(
      <LocaleProvider>
        <CalcSlider label="Ставка, % годовых" value={12.5} min={0.1} max={30} step={0.1} suffix="%" editable onChange={onChange} />
      </LocaleProvider>,
    );
    const field = screen.getByLabelText('Ввести число: Ставка, % годовых');
    expect(field.value).toBe('12,5');
    expect(screen.getByLabelText('Ставка, % годовых').getAttribute('aria-valuetext')).toBe('12,5%');
    // Допустимое число уходит в расчёт сразу, с запятой как разделителем.
    fireEvent.change(field, { target: { value: '9,8' } });
    expect(onChange).toHaveBeenLastCalledWith(9.8);
    // Слишком большое не ломает расчёт: при выходе из поля встаёт на максимум.
    fireEvent.change(field, { target: { value: '99' } });
    expect(onChange).toHaveBeenCalledTimes(1);
    fireEvent.blur(field);
    expect(onChange).toHaveBeenLastCalledWith(30);
    // Буквы игнорируются: значение не меняется.
    fireEvent.change(field, { target: { value: 'ааа' } });
    fireEvent.blur(field);
    expect(onChange).toHaveBeenCalledTimes(2);
  });
});
