import qbittorrentapi

client_instance: qbittorrentapi.Client |None = None
client_connection_settings: dict[str, str] = {}
client_initialized: bool = False

controller = None
started_shutdown = False
model_shutdown = False
view_shutdown = False

daemon_report_mode = True

callto_report_mode = False
