# Blender + OctaneRender (Testversion) + MCP-Server

Diese Anleitung verbindet Blender mit OctaneRender und mit Claude über den
MCP-Server [`mcp-for-blender`](https://github.com/ahujasid/mcp-for-blender)
(früher `blender-mcp`). Alle Schritte laufen **auf deinem eigenen Rechner**,
denn Blender, Octane und die GPU sind dort.

```
Claude (Desktop / Code) ──stdio──> uvx mcp-for-blender ──TCP :9876──> Blender-Add-on ──bpy──> OctaneRender
```

## Voraussetzungen

- NVIDIA-GPU mit aktuellem Treiber (Octane rendert nur auf CUDA/RTX).
- [uv](https://docs.astral.sh/uv/) für `uvx`:
  - macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows (PowerShell): `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

## 1. OctaneRender-Testversion installieren

1. Bei [OTOY](https://home.otoy.com/render/octane-render/) ein Konto anlegen
   und die Test-/Demo-Version **„Octane for Blender“** herunterladen
   (je nach Release ein fertiges Blender-Paket mit Octane oder ein Add-on für
   das offizielle Blender – nimm die Version, die zu deiner Blender-Version passt).
2. Installieren bzw. entpacken und dieses Blender starten.
3. Bei einem Add-on: *Bearbeiten → Einstellungen → Add-ons* → „Octane“ aktivieren.
4. Beim ersten Start mit dem OTOY-Konto anmelden, um die Testlizenz zu aktivieren.
5. Prüfen: *Eigenschaften → Render → Render-Engine* zeigt **Octane**.
   Alternativ `tools/mcp_octane/octane_check.py` ausführen.

## 2. MCP-Server und Blender-Add-on installieren

Am einfachsten mit dem Installer (richtet Claude Desktop/Claude Code ein und
installiert/aktiviert das Blender-Add-on):

```bash
uvx mcp-for-blender setup
```

Manuell:

```bash
uvx mcp-for-blender install-addon        # kopiert das Add-on in den Blender-Add-on-Ordner
uvx mcp-for-blender addon-paths          # zeigt gefundene Add-on-Ordner
```

Wenn Octane ein eigenes Blender-Paket mitbringt, muss das Add-on in **dessen**
Add-on-Ordner landen. Falls es nicht automatisch gefunden wird:

```bash
BLENDERMCP_ADDONS_DIR="/pfad/zu/octane-blender/<version>/scripts/addons" uvx mcp-for-blender install-addon
```

Dann in Blender *Einstellungen → Add-ons* → **„MCP for Blender“** aktivieren.
Im 3D-Viewport `N` drücken → Reiter **MCP for Blender** → ggf.
**Start MCP Server** (Port 9876).

## 3. Claude verbinden

- **Claude Code:** Dieses Repository enthält `.mcp.json` im Wurzelverzeichnis.
  `claude` im Repo starten und den Server „blender“ bestätigen (`/mcp` zeigt den Status).
- **Claude Desktop:** in `claude_desktop_config.json` eintragen
  (macOS: `~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\`):

  ```json
  {
    "mcpServers": {
      "blender": {
        "command": "uvx",
        "args": ["mcp-for-blender"],
        "env": { "BLENDER_MCP_DISABLE_TELEMETRY": "true" }
      }
    }
  }
  ```

  Danach Claude Desktop komplett beenden und neu starten.

## 4. Testen

In Claude z. B. fragen:

> Stelle die Render-Engine auf Octane, füge eine Kugel mit Glasmaterial hinzu
> und rendere ein Vorschaubild.

Claude nutzt dafür das Tool `execute_blender_code`, intern etwa:

```python
import bpy
bpy.context.scene.render.engine = 'octane'
```

## Hinweise

- Der Socket des Add-ons hat **keine Authentifizierung** – nur auf `localhost`
  lassen und nicht ins Netz freigeben.
- `execute_blender_code` führt beliebigen Python-Code in Blender aus. Vor
  wichtigen Szenen speichern.
- Die Octane-Testversion kann Einschränkungen haben (z. B. Wasserzeichen,
  begrenzte Laufzeit oder GPU-Anzahl) – siehe Bedingungen von OTOY.
