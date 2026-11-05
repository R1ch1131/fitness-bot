import { useCallback, useEffect, useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown } from 'lucide-react';
import './DarkSelect.css';

type Option = { value: string; label: string; icon?: ReactNode };
type Props = { label: string; value: string; options: Option[]; onChange: (value: string) => void; disabled?: boolean; compact?: boolean };

export function DarkSelect({ label, value, options, onChange, disabled = false, compact = false }: Props) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [position, setPosition] = useState<{ left: number; top: number; width: number; maxHeight: number } | null>(null);
  const selected = Math.max(0, options.findIndex(option => option.value === value));

  const place = useCallback(() => {
    const bounds = trigger.current?.getBoundingClientRect();
    if (!bounds) return;
    const width = Math.min(Math.max(bounds.width, compact ? 220 : 0), window.innerWidth - 24);
    const height = Math.min(options.length * 44 + 12, 280);
    const below = window.innerHeight - bounds.bottom - 12;
    const above = bounds.top - 12;
    const upwards = below < height && above > below;
    const maxHeight = Math.min(height, Math.max(90, upwards ? above - 6 : below - 6));
    setPosition({ left: Math.max(12, Math.min(bounds.left, window.innerWidth - width - 12)),
      top: upwards ? bounds.top - maxHeight - 6 : bounds.bottom + 6, width, maxHeight });
  }, [compact, options.length]);

  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (!trigger.current?.contains(event.target as Node) && !menu.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', outside);
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    return () => { document.removeEventListener('pointerdown', outside); window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true); };
  }, [open, place]);

  useEffect(() => {
    if (open) menu.current?.querySelector<HTMLElement>(`[data-option-index="${active}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [active, open]);

  const choose = (index: number) => { onChange(options[index].value); setOpen(false); trigger.current?.focus(); };

  return <>
    <button ref={trigger} type="button" role="combobox" aria-label={label} aria-haspopup="listbox" aria-expanded={open}
      aria-controls={open ? id : undefined} aria-activedescendant={open ? `${id}-${active}` : undefined} disabled={disabled}
      className={`dark-select ${compact ? 'is-compact' : ''} ${open ? 'is-open' : ''}`}
      onBlur={() => setOpen(false)}
      onClick={() => { if (!open) { setActive(selected); place(); } setOpen(previous => !previous); }}
      onKeyDown={event => {
        if (event.key === 'Escape' && open) { event.preventDefault(); event.stopPropagation(); setOpen(false); return; }
        if (event.key === 'Tab') { setOpen(false); return; }
        if (['ArrowDown', 'ArrowUp', 'Home', 'End', 'Enter', ' '].includes(event.key)) {
          event.preventDefault(); event.stopPropagation();
          if (!open) { setActive(event.key === 'End' ? options.length - 1 : event.key === 'Home' ? 0 : selected); place(); setOpen(true); }
          else if (event.key === 'Enter' || event.key === ' ') choose(active);
          else setActive(current => event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1 : (current + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length);
        }
      }}>
      <span className="dark-select-value">{options[selected]?.icon}<span>{options[selected]?.label}</span></span><ChevronDown size={15} className="dark-select-chevron" />
    </button>
    {open && position && createPortal(<div ref={menu} id={id} role="listbox" aria-label={label} className="dark-select-menu" style={position}
      onMouseDown={event => event.preventDefault()}>
      {options.map((option, index) => <div key={option.value} id={`${id}-${index}`} role="option" aria-selected={option.value === value}
        data-option-index={index} className={`dark-select-option ${active === index ? 'is-active' : ''} ${option.value === value ? 'is-selected' : ''}`}
        onPointerMove={() => setActive(index)} onClick={() => choose(index)}>
        <span className="dark-select-option-content">{option.icon}<span>{option.label}</span></span>{option.value === value && <Check size={15} />}
      </div>)}
    </div>, document.body)}
  </>;
}
