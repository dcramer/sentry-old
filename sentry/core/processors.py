class Processor(object):
    def process(self, data):
        resp = self.get_data(data)
        if resp:
            data['extra'].update(resp)
        return data
    
    def get_data(self, data):
        return {}