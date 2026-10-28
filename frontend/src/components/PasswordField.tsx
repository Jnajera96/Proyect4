import { useState } from "react";

export function PasswordField({ name, label, autoComplete = "current-password", minLength = 12 }: {
  name: string; label: string; autoComplete?: string; minLength?: number;
}) {
  const [visible, setVisible] = useState(false);
  return <div className="profile-password-field">
    <label htmlFor={`profile-${name}`}>{label}</label>
    <div className="profile-password-controls">
      <input id={`profile-${name}`} name={name} type={visible ? "text" : "password"}
        required minLength={minLength} maxLength={name === "recovery_code" ? 128 : 1024}
        autoComplete={autoComplete} spellCheck={false} autoCapitalize="none" />
      <button type="button" aria-label={`${visible ? "Ocultar" : "Mostrar"} ${label.toLowerCase()}`}
        aria-pressed={visible} onClick={() => setVisible(!visible)}>{visible ? "Ocultar" : "Mostrar"}</button>
    </div>
  </div>;
}
