import type { Shot } from '../types/shot';
import { getShotKind } from '../types/shot';

/** Reference devices for validating golf ball and club speeds. */
export const GOLF_COMPARATOR_DEVICES: readonly string[] = Object.freeze([
  'Stack Radar',
  'PRGR',
  'TrackMan',
  'Full Swing',
  'Other',
]);

/** Radar guns used to validate pitch speeds. */
export const PITCH_COMPARATOR_DEVICES: readonly string[] = Object.freeze(['Pocket Radar', 'Stalker', 'Other']);

/** Devices offered for a shot; a saved device missing from the list is kept so it still shows. */
export function comparatorDevicesFor(shot: Shot, savedDevice = ''): string[] {
  const devices = getShotKind(shot) === 'pitch-speed' ? PITCH_COMPARATOR_DEVICES : GOLF_COMPARATOR_DEVICES;
  return savedDevice && !devices.includes(savedDevice) ? [...devices, savedDevice] : [...devices];
}
