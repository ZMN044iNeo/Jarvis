// Moonraker Proxy Backend Function
// Provides HTTP-accessible proxy to Moonraker API for workflows, Telegram, and external integrations.

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
  let url = 'http://localhost:7125';
  let apiKey: string | undefined;
  try { if (typeof process !== 'undefined' && process.env && process.env.MOONRAKER_URL) url = process.env.MOONRAKER_URL; } catch (e) {}
  try { if (typeof process !== 'undefined' && process.env && process.env.MOONRAKER_API_KEY) apiKey = process.env.MOONRAKER_API_KEY; } catch (e) {}
  if (req.moonraker_url) url = req.moonraker_url;
  if (req.api_key) apiKey = req.api_key;

  if (!req.command) {
    return { success: false, error: 'Missing "command" field.' };
  }

  const hdrs: Record<string, string> = { 'Content-Type': 'application/json' };
  if (apiKey) hdrs['X-Api-Key'] = apiKey;

  async function go(endpoint: string, method?: string, body?: any) {
    const opts: any = { method: method || 'GET', headers: hdrs };
    if (body) opts.body = JSON.stringify(body);
    const resp = await fetch(url + endpoint, opts);
    const data = await resp.json();
    return { ok: resp.ok, data };
  }

  try {
    switch (req.command) {
      case 'status': {
        const objs = 'extruder,heater_bed,toolhead,gcode_move,print_stats,virtual_sdcard,display_status';
        const res = await go(`/printer/objects/query?${objs}`);
        const infoRes = await go(`/printer/info`);
        const temps = (res.data && res.data.result && res.data.result.status) || {};
        const pi = (infoRes.data && infoRes.data.result) || {};
        const ex = temps.extruder || {};
        const bed = temps.heater_bed || {};
        const ps = temps.print_stats || {};
        const gm = temps.gcode_move || {};
        const vs = temps.virtual_sdcard || {};
        const ds = temps.display_status || {};
        const gp = gm.gcode_position || [0,0,0,0];
        return {
          success: true,
          data: {
            state: pi.state || 'unknown',
            state_message: pi.state_message || '',
            hostname: pi.hostname || '',
            temperatures: { extruder: { actual: ex.temperature||0, target: ex.target||0 }, bed: { actual: bed.temperature||0, target: bed.target||0 } },
            position: { x: gp[0]||0, y: gp[1]||0, z: gp[2]||0, e: gp[3]||0 },
            print_progress: {
              filename: ps.filename||'', state: ps.state||'', progress: vs.progress||0,
              print_duration: ps.print_duration||0, total_duration: ps.total_duration||0,
              filament_used: ps.filament_used||0, message: ps.message||''
            },
            speed: ds.progress||0
          }
        };
      }
      case 'info': {
        const s = await go('/server/info');
        const p = await go('/printer/info');
        return { success: true, data: { server: (s.data&&s.data.result)||{}, printer: (p.data&&p.data.result)||{} } };
      }
      case 'send_gcode': {
        if (!req.gcode) return { success: false, error: 'Missing gcode' };
        const r = await go('/printer/gcode/script', 'POST', { script: req.gcode });
        return { success: r.ok, data: r.data, gcode_sent: req.gcode };
      }
      case 'start': {
        if (!req.filename) return { success: false, error: 'Missing filename' };
        const r = await go(`/printer/print/start?filename=${encodeURIComponent(req.filename)}`, 'POST');
        return { success: r.ok, data: r.data, filename: req.filename };
      }
      case 'pause': { const r = await go('/printer/print/pause','POST'); return { success: r.ok, data: r.data }; }
      case 'resume': { const r = await go('/printer/print/resume','POST'); return { success: r.ok, data: r.data }; }
      case 'cancel': { const r = await go('/printer/print/cancel','POST'); return { success: r.ok, data: r.data }; }
      case 'estop': { const r = await go('/printer/emergency_stop','POST'); return { success: r.ok, data: r.data }; }
      case 'files': { const r = await go('/server/files/list?root=gcodes'); return { success: r.ok, data: (r.data&&r.data.result)||[] }; }
      case 'webcams': { const r = await go('/server/webcams/list'); return { success: r.ok, data: (r.data&&r.data.result&&r.data.result.webcams)||[] }; }
      case 'jobs': { const r = await go('/server/history/list?limit=50'); return { success: r.ok, data: (r.data&&r.data.result)||{} }; }
      case 'power': {
        if (!req.device) { const r = await go('/machine/device_power/devices'); return { success: r.ok, data: (r.data&&r.data.result)||{} }; }
        if (req.action) { const r = await go(`/machine/device_power/device?device=${encodeURIComponent(req.device)}&action=${req.action}`,'POST'); return { success: r.ok, data: (r.data&&r.data.result)||{} }; }
        const r = await go(`/machine/device_power/device?device=${encodeURIComponent(req.device)}`); return { success: r.ok, data: (r.data&&r.data.result)||{} };
      }
      default: return { success: false, error: `Unknown command: ${req.command}` };
    }
  } catch (err: any) {
    return { success: false, error: 'Proxy error', details: (err&&err.message)||'Unknown' };
  }
}
