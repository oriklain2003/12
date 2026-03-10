/**
 * Specialized editor for epoch-seconds values displayed as datetime-local.
 * Converts between epoch seconds string and native datetime-local format.
 */

interface DateTimeInputProps {
  value: string | undefined;
  onChange: (epochStr: string) => void;
  placeholder?: string;
}

function epochToLocal(epoch: string): string {
  const seconds = Number(epoch);
  if (Number.isNaN(seconds) || seconds <= 0) return '';
  const date = new Date(seconds * 1000);
  // datetime-local expects YYYY-MM-DDTHH:mm
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function localToEpoch(local: string): string {
  if (!local) return '';
  return String(Math.floor(new Date(local).getTime() / 1000));
}

export function DateTimeInput({ value, onChange, placeholder }: DateTimeInputProps) {
  return (
    <div className="datetime-input nodrag nowheel">
      <input
        type="datetime-local"
        value={epochToLocal(value ?? '')}
        placeholder={placeholder}
        onChange={(e) => {
          const epoch = localToEpoch(e.target.value);
          onChange(epoch);
        }}
      />
    </div>
  );
}
