// Moonraker Proxy Backend Function
// Provides HTTP-accessible proxy to Moonraker API for workflows, Telegram, and external integrations.
// Deploy this function to make printer commands callable via HTTP.

interface RequestBody {
  command: 'status' | 'info' | 'send_gcode' | 'start' | 'pause' | 'resume' | 'cancel' | 'estop' | 'files' | 'webcams' | 'jobs' | 'power';
  gcode?: string;
  filename?: string;
  device?: string;
  action?: 'on' | 'off';
  moonraker_url?: string;
  api_key?: string;
}

export default async function handler(req: RequestBody) {
  const MOONRAKER_URL = req.moonraker_url || process.env.MOONRAKER_URL || 'http://localhost:7125';
  const API_KEY = req.api_key || process.env.MOONRAKER_API_KEY;
  const TIMEOUT_MS = 10000;

  if (!req.command) {
    return { success: false, error: 'Missing "command" field. Valid commands: status, info, send_gcode, start, pause, resume, cancel, estop, files, webcams, jobs, power' };
  }

  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (API_KEY) headers['X-Api-Key'] = API_KEY;

  async function fetchWithTimeout(url: string, options: any = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
    try {
      const response = await fetch(url, { ...options, headers: { ...headers, ...(options.headers || {}) }, signal: controller.signal });
      const data = await response.json();
      return { ok: response.ok, status: response.status, data };
    } catch (err: any) {
      if (err.name === 'AbortError') {
        return { ok: false, status: 408, data: { error: 'Request timed out', url } };
      }
      return { ok: false, status: 0, data: { error: err.message, url } };
    } finally {
      clearTimeout(timeout);
    }
  }

  try {
    let result: any;

    switch (req.command) {
      case 'status': {
        // Query multiple printer objects in one call
        const objs = 'extruder,heater_bed,toolhead,gcode_move,print_stats,virtual_sdcard,display_status,fans';
        const res = await fetchWithTimeout(`${MOONRAKER_URL}/printer/objects/query?${objs}`);
        const infoRes = await fetchWithTimeout(`${MOONRAKER_URL}/printer/info`);
        const temps = res.data?.result?.status || {};
        const printerInfo = infoRes.data?.result || {};
        
        const extruder = temps.extruder || {};
        const bed = temps.heater_bed || {};
        const printStats = temps.print_stats || {};
        const gcodeMove = temps.gcode_move || {};
        const toolhead = temps.toolhead || {};
        const virtualSd = temps.virtual_sdcard || {};
        const displayStatus = temps.display_status || {};

        result = {
          success: true,
          data: {
            state: printerInfo.state || 'unknown',
            state_message: printerInfo.state_message || '',
            hostname: printerInfo.hostname || '',
            temperatures: {
              extruder: { actual: extruder.temperature ?? 0, target: extruder.target ?? 0, power: extruder.power ?? 0 },
              bed: { actual: bed.temperature ?? 0, target: bed.target ?? 0, power: bed.power ?? 0 }
            },
            position: {
              x: gcodeMove.gcode_position?.[0] ?? 0,
              y: gcodeMove.gcode_position?.[1] ?? 0,
              z: gcodeMove.gcode_position?.[2] ?? 0,
              e: gcodeMove.gcode_position?.[3] ?? 0
            },
            print_progress: {
              filename: printStats.filename || '',
              state: printStats.state || '',
              progress: virtualSd.progress ?? 0,
              print_duration: printStats.print_duration ?? 0,
              total_duration: printStats.total_duration ?? 0,
              filament_used: printStats.filament_used ?? 0,
              message: printStats.message || '',
              remaining_time: calculateRemainingTime(printStats.print_duration, virtualSd.progress)
            },
            speed: displayStatus.progress ?? 0,
            fan_speed: temps.fans?.['fan']?.speed ?? 0
          }
        };
        break;
      }

      case 'info': {
        const [serverRes, printerRes] = await Promise.all([
          fetchWithTimeout(`${MOONRAKER_URL}/server/info`),
          fetchWithTimeout(`${MOONRAKER_URL}/printer/info`)
        ]);
        result = {
          success: true,
          data: {
            server: serverRes.data?.result || {},
            printer: printerRes.data?.result || {}
          }
        };
        break;
      }

      case 'send_gcode': {
        if (!req.gcode) {
          result = { success: false, error: 'Missing "gcode" field for send_gcode command' };
          break;
        }
        const res = await fetchWithTimeout(`${MOONRAKER_URL}/printer/gcode/script`, {
          method: 'POST',
          body: JSON.stringify({ script: req.gcode })
        });
        result = { success: res.ok, data: res.data, gcode_sent: req.gcode };
        break;
      }

      case 'start': {
        if (!req.filename) {
          result = { success: false, error: 'Missing "filename" field for start command' };
          break;
        }
        const res = await fetchWithTimeout(`${MOONRAKER_URL}/printer/print/start?filename=${encodeURIComponent(req.filename)}`, {
          method: 'POST'
        });
        result = { success: res.ok, data: res.data, filename: req.filename };
        break;
      }

      case 'pause': {
        const res = await fetchWithTimeout(`${MOONRAKER_URL}/printer/print/pause`, { method: 'POST' });
        result = { success: res.ok, data: res.data };
        break;
      }

      case 'resume': {
        const res = await fetchWithTimeout(`${MOONRAKER_URL}/printer/print/resume`, { method: 'POST' });
        result = { success: res.ok, data: res.data };
        break;
      }

      case 'cancel': {
        const res = await fetchWithTimeout(`${MOONRAKER_URL}/printer/print/cancel`, { method: 'POST' });
        result = { success: res.ok, data: res.data };
        break;
      }

      case 'estop': {
        const res = await fetchWithTimeout(`${MOONRAKER_URL}/printer/emergency_stop`, { method: 'POST' });
        result = { success: res.ok, data: res.data };
        break;
      }

      case 'files': {
        const res = await fetchWithTimeout(`${MOONRAKER_URL}/server/files/list?root=gcodes`);
        result = { success: res.ok, data: res.data?.result || [], count: (res.data?.result || []).length };
        break;
      }

      case 'webcams': {
        const res = await fetchWithTimeout(`${MOONRAKER_URL}/server/webcams/list`);
        result = { success: res.ok, data: res.data?.result?.webcams || [] };
        break;
      }

      case 'jobs': {
        const res = await fetchWithTimeout(`${MOONRAKER_URL}/server/history/list?limit=50`);
        result = { success: res.ok, data: res.data?.result || {} };
        break;
      }

      case 'power': {
        if (!req.device) {
          // List all power devices
          const res = await fetchWithTimeout(`${MOONRAKER_URL}/machine/device_power/devices`);
          result = { success: res.ok, data: res.data?.result || {} };
        } else if (req.action) {
          // Control a device
          const res = await fetchWithTimeout(`${MOONRAKER_URL}/machine/device_power/device?device=${req.device}&action=${req.action}`, {
            method: 'POST'
          });
          result = { success: res.ok, data: res.data?.result || {}, device: req.device, action: req.action };
        } else {
          // Get status of a specific device
          const res = await fetchWithTimeout(`${MOONRAKER_URL}/machine/device_power/device?device=${req.device}`);
          result = { success: res.ok, data: res.data?.result || {}, device: req.device };
        }
        break;
      }

      default:
        result = { success: false, error: `Unknown command: ${req.command}` };
    }

    return result;
  } catch (err) {
    return { success: false, error: 'Internal proxy error', details: err.message };
  }
}

function calculateRemainingTime(elapsed: number, progress: number): number | null {
  if (!progress || progress <= 0 || progress >= 1) return null;
  const totalTime = elapsed / progress;
  return Math.max(0, Math.round(totalTime - elapsed));
}
