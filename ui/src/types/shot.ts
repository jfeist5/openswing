export type SpinQuality = 'high' | 'medium' | 'low' | 'experimental' | 'withheld';

export interface CameraReplay {
  id: string;
  frame_count: number;
  trigger_frame: number;
  playback_fps: number;
  duration_seconds: number;
  display_mirror_horizontal: boolean;
}

export interface Shot {
  mode?: 'rolling-buffer' | 'mock' | 'swing-speed' | 'pitch-speed';
  shot_number?: number | null;
  ball_speed_mph: number;
  club_speed_mph: number | null;
  smash_factor: number | null;
  estimated_carry_yards: number;
  carry_range: [number, number];
  club: string;
  profile_id?: string;
  profile_name?: string;
  timestamp: string;
  impact_timestamp?: number | null;
  peak_magnitude: number | null;
  // Launch angle data (from K-LD7 radar (deprecated), camera, or estimation)
  launch_angle_vertical: number | null;
  launch_angle_horizontal: number | null;
  launch_angle_confidence: number | null;
  launch_angle_vertical_confidence?: number | null;
  launch_angle_horizontal_confidence?: number | null;
  launch_angle_vertical_source?: string | null;
  launch_angle_horizontal_source?: string | null;
  angle_source: 'radar' | 'camera' | 'estimated' | null;
  club_angle_deg: number | null;
  club_path_deg: number | null;
  experimental_attack_angle_deg?: number | null;
  experimental_attack_angle_status?: string | null;
  experimental_club_path_deg?: number | null;
  experimental_club_path_status?: string | null;
  experimental_fused_attack_angle_deg?: number | null;
  experimental_fused_club_path_deg?: number | null;
  experimental_fused_status?: string | null;
  experimental_fused_attack_angle_confidence?: 'high' | 'medium' | 'low' | 'withheld' | null;
  experimental_fused_club_path_confidence?: 'high' | 'medium' | 'low' | 'withheld' | null;
  experimental_camera_trace_deg?: number | null;
  experimental_aoa_offset_source?: string | null;
  iwr6843_horizontal_deg?: number | null;
  iwr6843_horizontal_confidence?: number | null;
  experimental_camera_horizontal_deg?: number | null;
  experimental_camera_horizontal_confidence?: number | null;
  experimental_camera_horizontal_status?: string | null;
  experimental_camera_iwr_delta_deg?: number | null;
  spin_axis_deg: number | null;
  // Rolling buffer mode spin data
  spin_rpm: number | null;
  spin_confidence: number | null;
  spin_quality: SpinQuality | null;
  spin_source: 'measured' | 'calculated' | null;
  spin_method?: string | null;
  spin_multipath_fade_hz?: number | null;
  carry_spin_adjusted: number | null;
  swing_speed_duration_ms?: number;
  swing_speed_reading_count?: number;
  swing_speed_trigger_mph?: number;
  training_implement?: string;
  training_implement_label?: string;
  camera_replay?: CameraReplay | null;
}

export interface SessionStats {
  shot_count: number;
  avg_ball_speed: number;
  max_ball_speed: number;
  min_ball_speed: number;
  std_dev?: number;
  avg_club_speed: number | null;
  avg_smash_factor: number | null;
  avg_carry_est: number;
  // Rolling buffer mode spin stats
  avg_spin_rpm?: number | null;
  spin_detection_rate?: number;
  mode?: 'rolling-buffer';
}

export interface SessionState {
  stats: SessionStats;
  shots: Shot[];
  club?: string;
}

export interface TriggerDiagnostic {
  timestamp: string;
  trigger_type: string;
  accepted: boolean;
  reason: string;
  response_bytes: number;
  total_readings: number;
  outbound_readings: number;
  inbound_readings: number;
  peak_outbound_mph: number;
  peak_inbound_mph: number;
  all_outbound_speeds: number[];
  all_inbound_speeds: number[];
  peak_outbound_magnitude: number;
  peak_inbound_magnitude: number;
  latency_ms: number | null;
  // Present when accepted (shot created):
  ball_speed_mph?: number | null;
  club_speed_mph?: number | null;
  spin_rpm?: number | null;
  carry_yards?: number | null;
  iwr6843?: IWR6843Diagnostic;
}

export type IWR6843DiagnosticState = 'accepted' | 'rejected' | 'error';

export interface IWR6843Diagnostic {
  state: IWR6843DiagnosticState;
  reason: string;
  angle_deg?: number;
}

export interface TriggerDiagnosticUpdate {
  timestamp: string;
  iwr6843: IWR6843Diagnostic;
}

export interface TriggerStatus {
  /** 'connecting' is UI-only: the server has not reported its mode yet. */
  mode: 'connecting' | 'rolling-buffer' | 'mock' | 'swing-speed' | 'pitch-speed';
  trigger_type: string | null;
  radar_connected: boolean;
  radar_port: string | null;
  triggers_total: number;
  triggers_accepted: number;
  triggers_rejected: number;
}

export interface SpeedStats {
  count: number;
  last_speed_mph: number;
  best_speed_mph: number;
  avg_speed_mph: number;
}

export type SwingSpeedStats = SpeedStats;

export interface SpeedStatsFilter {
  profileId?: string | null;
  trainingImplement?: string | null;
  club?: string | null;
}

export type SwingSpeedStatsFilter = SpeedStatsFilter;

/** Ball strikes come from the rolling buffer; speed-only kinds are radar-gun peaks with no ball flight. */
export type ShotKind = 'ball-strike' | 'swing-speed' | 'pitch-speed';
export type SpeedOnlyShotKind = Exclude<ShotKind, 'ball-strike'>;

export function getShotKind(shot: Shot): ShotKind {
  if (shot.mode === 'pitch-speed') return 'pitch-speed';
  if (shot.mode === 'swing-speed' || shot.club === 'Swing Speed') return 'swing-speed';
  return 'ball-strike';
}

export function isSpeedOnlyKind(kind: ShotKind): kind is SpeedOnlyShotKind {
  return kind !== 'ball-strike';
}

export function isSwingSpeedShot(shot: Shot | null): boolean {
  return shot !== null && getShotKind(shot) === 'swing-speed';
}

export function isPitchSpeedShot(shot: Shot | null): boolean {
  return shot !== null && getShotKind(shot) === 'pitch-speed';
}

/** Peak speed of a speed-only shot; the server stamps it on club speed. */
export function getPeakSpeedMph(shot: Shot): number {
  return shot.club_speed_mph ?? shot.ball_speed_mph;
}

export const getSwingSpeedMph = getPeakSpeedMph;

export function filterShotsByProfile(shots: Shot[], profileId: string): Shot[] {
  if (!profileId) return [];
  return shots.filter((shot) => shot.profile_id === profileId);
}

export function excludeShotsByProfile(shots: Shot[], profileId: string): Shot[] {
  if (!profileId) return shots;
  return shots.filter((shot) => shot.profile_id !== profileId);
}

function normalizeToken(value: string | null | undefined): string {
  return (value?.trim() || '').toLowerCase();
}

export function filterSpeedShots(shots: Shot[], kind: SpeedOnlyShotKind, filter: SpeedStatsFilter = {}): Shot[] {
  const scoped = filter.profileId ? filterShotsByProfile(shots, filter.profileId) : shots;
  const trainingImplement = normalizeToken(filter.trainingImplement);
  const club = normalizeToken(filter.club);

  return scoped.filter((shot) => {
    if (getShotKind(shot) !== kind) {
      return false;
    }

    if (trainingImplement) {
      const shotImplement = normalizeToken(shot.training_implement);
      const shotImplementLabel = normalizeToken(shot.training_implement_label);
      const shotClub = normalizeToken(shot.club);

      return (
        shotImplement === trainingImplement ||
        shotImplementLabel === trainingImplement ||
        shotClub === trainingImplement
      );
    }

    if (club && normalizeToken(shot.club) !== club) {
      return false;
    }

    return true;
  });
}

export function filterSwingSpeedShots(shots: Shot[], filter: SpeedStatsFilter = {}): Shot[] {
  return filterSpeedShots(shots, 'swing-speed', filter);
}

export function computeSpeedStats(shots: Shot[], kind: SpeedOnlyShotKind, filter: SpeedStatsFilter = {}): SpeedStats {
  const speeds = filterSpeedShots(shots, kind, filter).map(getPeakSpeedMph);

  if (speeds.length === 0) {
    return {
      count: 0,
      last_speed_mph: 0,
      best_speed_mph: 0,
      avg_speed_mph: 0,
    };
  }

  const total = speeds.reduce((sum, speed) => sum + speed, 0);

  return {
    count: speeds.length,
    last_speed_mph: speeds[speeds.length - 1],
    best_speed_mph: Math.max(...speeds),
    avg_speed_mph: total / speeds.length,
  };
}

/** The speed-only kind shared by every shot, or null for an empty or mixed/ball-strike list. */
export function getSpeedSessionKind(shots: Shot[]): SpeedOnlyShotKind | null {
  if (shots.length === 0) return null;
  const kind = getShotKind(shots[0]);
  if (!isSpeedOnlyKind(kind)) return null;
  return shots.every((shot) => getShotKind(shot) === kind) ? kind : null;
}

export function computeSwingSpeedStats(shots: Shot[], filter: SpeedStatsFilter = {}): SpeedStats {
  return computeSpeedStats(shots, 'swing-speed', filter);
}

/**
 * Compute session stats from an array of shots.
 */
export function computeStats(shots: Shot[]): SessionStats {
  if (shots.length === 0) {
    return {
      shot_count: 0,
      avg_ball_speed: 0,
      max_ball_speed: 0,
      min_ball_speed: 0,
      avg_club_speed: null,
      avg_smash_factor: null,
      avg_carry_est: 0,
    };
  }

  const ballSpeeds = shots.map((s) => s.ball_speed_mph);
  const clubSpeeds = shots.map((s) => s.club_speed_mph).filter((v): v is number => v !== null);
  const smashFactors = shots.map((s) => s.smash_factor).filter((v): v is number => v !== null);
  const carries = shots.map((s) => s.estimated_carry_yards);

  const mean = (arr: number[]) => arr.reduce((a, b) => a + b, 0) / arr.length;
  const stdDev = (arr: number[]) => {
    if (arr.length < 2) return 0;
    const m = mean(arr);
    return Math.sqrt(arr.reduce((sum, x) => sum + (x - m) ** 2, 0) / (arr.length - 1));
  };

  return {
    shot_count: shots.length,
    avg_ball_speed: mean(ballSpeeds),
    max_ball_speed: Math.max(...ballSpeeds),
    min_ball_speed: Math.min(...ballSpeeds),
    std_dev: stdDev(ballSpeeds),
    avg_club_speed: clubSpeeds.length > 0 ? mean(clubSpeeds) : null,
    avg_smash_factor: smashFactors.length > 0 ? mean(smashFactors) : null,
    avg_carry_est: mean(carries),
  };
}

/**
 * Get unique clubs from shots array.
 */
export function getUniqueClubs(shots: Shot[]): string[] {
  const clubs = new Set(shots.map((s) => s.club));
  return Array.from(clubs);
}
