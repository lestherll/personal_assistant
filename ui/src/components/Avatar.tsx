const PALETTE = [
  "bg-violet-500",
  "bg-indigo-500",
  "bg-cyan-600",
  "bg-teal-600",
  "bg-fuchsia-500",
  "bg-sky-600",
];

function hashColor(name: string): string {
  let sum = 0;
  for (let i = 0; i < name.length; i++) sum += name.charCodeAt(i);
  return PALETTE[sum % PALETTE.length];
}

interface Props {
  name: string;
  size?: "sm" | "md";
}

export function Avatar({ name, size = "md" }: Props) {
  const color = hashColor(name);
  const letter = name.charAt(0).toUpperCase();
  const dim = size === "sm" ? "h-6 w-6 text-xs" : "h-8 w-8 text-sm";
  return (
    <span
      className={`inline-flex flex-shrink-0 items-center justify-center rounded-full font-semibold text-white ${color} ${dim}`}
      aria-hidden="true"
    >
      {letter}
    </span>
  );
}
