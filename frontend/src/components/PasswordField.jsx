// Поле пароля с кнопкой «показать»: на телефоне легко проверить, что набрано без опечаток.
// Подпись, подсказка и состояние ошибки задаёт страница; кнопка 44 px, не уходит за край поля.
import { useId, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { useT } from '../i18n';
import '../styles/w5-pages.css';

export default function PasswordField({
  label, value, onChange, autoComplete, minLength, invalid = false, describedBy, placeholder, className,
}) {
  const t = useT();
  const id = useId();
  const [shown, setShown] = useState(false);
  return (
    <div>
      <label className="mb-1.5 block text-sm text-text-secondary" htmlFor={id}>{label}</label>
      <div className="w5-pass">
        <input
          id={id}
          name="password"
          type={shown ? 'text' : 'password'}
          required
          minLength={minLength}
          value={value}
          onChange={onChange}
          autoComplete={autoComplete}
          placeholder={placeholder}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          className={className}
        />
        <button
          type="button"
          className="w5-pass__toggle"
          onClick={() => setShown((prev) => !prev)}
          aria-pressed={shown}
          aria-label={shown ? t('w5.auth.hidePassword') : t('w5.auth.showPassword')}
        >
          {shown ? <EyeOff className="h-[18px] w-[18px]" aria-hidden="true" /> : <Eye className="h-[18px] w-[18px]" aria-hidden="true" />}
        </button>
      </div>
    </div>
  );
}
