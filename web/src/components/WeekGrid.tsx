import { useCallback, useRef, useState } from "react";
import type { AuditCell, Day } from "../api/types";
import { DAYS, HOURS, blockKey, cellVars, hourLabel, pct } from "../lib/scale";
import { useTranslation } from "react-i18next";

/**
 * WeekGrid — days (columns) x clinic hours (rows, 07..18). A real <table> with
 * row/column headers; each cell is a button whose accessible name states the
 * day, hour and share (accessibility.md).
 *
 * Moving a block:
 *  - Mouse: drag a cell onto another cell in the SAME day column; drops on that
 *    hour.
 *  - Keyboard: focus a cell, Enter picks it up, arrow keys move within the day
 *    column, Enter drops on the new hour, Esc cancels (2.5.7 drag alternative).
 * Either way we call onMove(blockKey(day, fromHour), toHour).
 */
export function WeekGrid({
  cells,
  busy,
  pickedBlock,
  onCellFocus,
  onMove,
}: {
  cells: AuditCell[];
  busy: boolean;
  /** block key currently picked up for a keyboard move, or null */
  pickedBlock: string | null;
  onCellFocus: (day: Day, hour: number) => void;
  onMove: (block: string, toHour: number) => void;
}) {
  const { t } = useTranslation();
  const byKey = new Map(cells.map((c) => [blockKey(c.day, c.hour), c]));
  // Only show the days the clinic actually runs; a week of empty columns reads as
  // broken. Fall back to the full week when no cell has data.
  const withData = DAYS.filter((d) => cells.some((c) => c.day === d));
  const days = withData.length > 0 ? withData : DAYS;
  const [picked, setPicked] = useState<{ day: Day; hour: number } | null>(null);
  const dragFrom = useRef<{ day: Day; hour: number } | null>(null);

  const cellName = useCallback(
    (day: Day, hour: number, c: AuditCell | undefined) => {
      const dayName = t(`audit.days.${day}`);
      return c
        ? t("audit.cellName", {
            day: dayName,
            hour: hourLabel(hour),
            pct: Math.round(c.share * 100),
            n: c.n,
          })
        : t("audit.cellNoData", { day: dayName, hour: hourLabel(hour) });
    },
    [t],
  );

  const focusCell = (day: Day, hour: number) => {
    const el = document.getElementById(`cell-${blockKey(day, hour)}`);
    el?.focus();
  };

  const onKeyDown = (
    e: React.KeyboardEvent<HTMLButtonElement>,
    day: Day,
    hour: number,
  ) => {
    const dIdx = days.indexOf(day);
    const hIdx = HOURS.indexOf(hour);
    switch (e.key) {
      case "ArrowRight":
        e.preventDefault();
        if (dIdx < days.length - 1) focusCell(days[dIdx + 1], hour);
        break;
      case "ArrowLeft":
        e.preventDefault();
        if (dIdx > 0) focusCell(days[dIdx - 1], hour);
        break;
      case "ArrowDown":
        e.preventDefault();
        if (hIdx < HOURS.length - 1) focusCell(day, HOURS[hIdx + 1]);
        break;
      case "ArrowUp":
        e.preventDefault();
        if (hIdx > 0) focusCell(day, HOURS[hIdx - 1]);
        break;
      case "Enter":
      case " ":
        e.preventDefault();
        if (picked == null) {
          setPicked({ day, hour });
        } else {
          // drop: move the picked block (its day) to this row's hour
          if (hour !== picked.hour) {
            onMove(blockKey(picked.day, picked.hour), hour);
          }
          setPicked(null);
        }
        break;
      case "Escape":
        if (picked) {
          e.preventDefault();
          setPicked(null);
        }
        break;
      default:
        break;
    }
  };

  return (
    <table className="weekgrid" aria-busy={busy}>
      <caption className="visually-hidden">{t("audit.gridCaption")}</caption>
      <thead>
        <tr>
          <th scope="col">{t("audit.hour")}</th>
          {days.map((d) => (
            <th scope="col" key={d}>
              <abbr title={t(`audit.days.${d}`)}>{t(`audit.dayShort.${d}`)}</abbr>
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {HOURS.map((hour) => (
          <tr key={hour}>
            <th scope="row">{hourLabel(hour)}</th>
            {days.map((day) => {
              const key = blockKey(day, hour);
              const c = byKey.get(key);
              const vars = cellVars(c ? c.share : null);
              const isPicked =
                (picked?.day === day && picked?.hour === hour) ||
                pickedBlock === key;
              return (
                <td key={key}>
                  <button
                    id={`cell-${key}`}
                    type="button"
                    className={`cell-btn${isPicked ? " picked" : ""}`}
                    style={vars as React.CSSProperties}
                    aria-label={cellName(day, hour, c)}
                    aria-pressed={isPicked}
                    draggable={!busy}
                    onFocus={() => onCellFocus(day, hour)}
                    onMouseEnter={() => onCellFocus(day, hour)}
                    onKeyDown={(e) => onKeyDown(e, day, hour)}
                    onDragStart={() => {
                      dragFrom.current = { day, hour };
                    }}
                    onDragOver={(e) => {
                      if (dragFrom.current?.day === day) e.preventDefault();
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      const from = dragFrom.current;
                      dragFrom.current = null;
                      if (from && from.day === day && from.hour !== hour) {
                        onMove(blockKey(from.day, from.hour), hour);
                      }
                    }}
                  >
                    {c ? pct(c.share) : "—"}
                  </button>
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
