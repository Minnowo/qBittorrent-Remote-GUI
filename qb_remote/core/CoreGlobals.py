import qbittorrentapi

client_instance: qbittorrentapi.Client = None
client_connection_settings: dict = None
client_initialized: bool = False

controller = None
started_shutdown = False
model_shutdown = False
view_shutdown = False

daemon_report_mode = True

callto_report_mode = False
