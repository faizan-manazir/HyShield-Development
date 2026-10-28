from cowrie.commands.bridge_base import BridgeCommand


class Command_pwd(BridgeCommand):

    def start(self):

        self.run_bridge("pwd")

