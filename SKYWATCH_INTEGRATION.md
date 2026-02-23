# SkyWatch Integration Guide

You can now stream live images from SkyWatch directly to your web dashboard!

## Quick Setup in SkyWatch

Configure SkyWatch to upload images via FTP:

### In SkyWatch → Options → Image → FTP:
- **Enable FTP upload**: ✓ Check
- **Host/IP address**: `10.0.0.100`
- **Port**: `2121`
- **Username**: `skywatch`
- **Password**: (leave empty)
- **Use Passive mode**: ✓ Check
- **Remote folder**: `/` (root)

### Update interval
Set "Update interval" to 60 seconds for live updates

### Test
Click "Test" in SkyWatch - if successful, images will start appearing in your dashboard!

## What Happens

When SkyWatch uploads an image:

1. **FTP Receiver** (port 2121) captures the file
2. **Latest image** is copied to `/srv/doro_lab_projects/skycam/sky_latest_web.jpg`
3. **Archive** - images stored by date in `/srv/doro_lab_projects/skycam/archive/YYYY/MM/DD/`
4. **Gallery** - recent images in `/srv/doro_lab_projects/skycam/images/skywatch/`
5. **Dashboard** - refreshes automatically with latest image
6. **Forecast** - if metadata included, weather data is merged

## Dashboard Display

Your dashboard will now show:

- ✅ **Live moon/sky images** - Real-time from SkyWatch camera
- ✅ **Camera status** - Connection indicator on forecast page
- ✅ **Auto-updated gallery** - Last 12 SkyWatch images
- ✅ **Weather integration** - Camera temperature + humidity from SkyWatch

## Monitoring

Check FTP receiver logs:
```bash
sudo journalctl -u skywatch-ftp-receiver.service -f
```

View SkyWatch connection status:
```bash
cat /srv/doro_lab_projects/skycam/skywatch_status.json
```

List recent images:
```bash
ls -lh /srv/doro_lab_projects/skycam/images/skywatch/ | tail -20
```

## Advanced: Image Archive

All images are archived with date structure:
```
/srv/doro_lab_projects/skycam/archive/2026/02/16/sky_20260216_HHMMSS.jpg
```

This allows for:
- Historical image review
- Time-lapse sequences
- Weather pattern analysis
- Long-term moon mapping

## Troubleshooting

**Images not uploading?**
- Verify IP address: `10.0.0.100` (your server IP)
- Verify port: `2121` (custom FTP port)
- Check firewall: `sudo ufw allow 2121`
- Test connection: `telnet 10.0.0.100 2121`

**Connection keeps dropping?**
- Set longer interval in SkyWatch (e.g., 120 seconds)
- Enable Passive FTP mode
- Check network stability

**Files not showing in dashboard?**
- Verify file permissions: `ls -l /srv/doro_lab_projects/skycam/`
- Check logs: `sudo journalctl -u skywatch-ftp-receiver.service`
- Manual test: `curl http://10.0.0.100/skycam/latest.jpg`
