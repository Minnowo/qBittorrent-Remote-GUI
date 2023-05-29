
from . import CoreGlobals as CG
from . import CoreData as CD
from . import CoreConstants as CC
from . import CoreCaches as Cache
from . import CoreLogging as logging

class ClientController():


    def __init__(self) -> None:

        self.torrent_files_cache = Cache.Expiring_Data_Cache("torrent_files_cache", CC.TORRENT_CACHE_TIME_SECONDS)
        self.torrent_metadata_cache = Cache.Data_Cache("torrent_files_cache")

        expiring_data_caches = [self.torrent_files_cache]
        data_caches = [self.torrent_metadata_cache]




    def get_torrents(self, **kwargs):

        if kwargs is None:

            data = self.torrent_files_cache.get_if_has_non_expired_data("torrent_list")

            if data:
                logging.debug("Cache hit for 'torrent_list'")
                return data 
            else:
                logging.debug("Cache miss for 'torrent_list'")

            data = CG.client_instance.torrents_info(**kwargs)
            
            self.torrent_files_cache.add_data("torrent_list", data)

            return data

        logging.debug("Custom call to torrent_info, skipping cache")

        return CG.client_instance.torrents_info(**kwargs)




