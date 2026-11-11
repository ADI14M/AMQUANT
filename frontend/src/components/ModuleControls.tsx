import type { InputHTMLAttributes, SelectHTMLAttributes } from 'react'

export function NumberField({ label, unit, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; unit?: string }) {
  return <label className="control-field"><span>{label}</span><div className="input-wrap"><input type="number" {...props}/>{unit && <small>{unit}</small>}</div></label>
}

export function SelectField({ label, children, ...props }: SelectHTMLAttributes<HTMLSelectElement> & { label: string }) {
  return <label className="control-field"><span>{label}</span><select {...props}>{children}</select></label>
}

export function ResultMetric({ label, value, note }: { label: string; value: string; note?: string }) {
  return <div className="result-metric"><span>{label}</span><b>{value}</b>{note && <small>{note}</small>}</div>
}

export function RunButton({ loading, children = 'Run calculation' }: { loading: boolean; children?: string }) {
  return <button className="primary-button run-button" type="submit" disabled={loading}>{loading ? 'Calculating…' : children}</button>
}

export function ErrorMessage({ message }: { message: string | null }) {
  return message ? <div className="calc-error" role="alert">{message}</div> : null
}
