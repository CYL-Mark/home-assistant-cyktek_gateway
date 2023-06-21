
class ControllersMapSingleTon:
    """The singleTon class for CYL-Tek controller's map"""

    _instance = None
    _map=dict()

    @staticmethod
    def get_instance():
        if ControllersMapSingleTon._instance is None:
            ControllersMapSingleTon()
        return ControllersMapSingleTon._instance

    def __init__(self):
        if ControllersMapSingleTon._instance is not None:
            raise Exception('only one instance can exist')
        else:
            self._id = id(self)
            ControllersMapSingleTon._instance = self
    
    def get_id(self):
        return self._id

    def get_map(self):
        return self._map



def get_controllers_map():
    return ControllersMapSingleTon.get_instance().get_map()
    
