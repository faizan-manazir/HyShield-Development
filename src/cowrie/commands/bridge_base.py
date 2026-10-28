import socket

from cowrie.shell.command import HoneyPotCommand


class BridgeCommand(HoneyPotCommand):

    def run_bridge(self, full_command):

        try:

            client = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            )

            client.connect(
                ("127.0.0.1", 5050)
            )

            client.sendall(
                full_command.encode()
            )

            response = client.recv(
                65535
            ).decode()

            client.close()

            if response:

                self.write(response)

        except Exception as e:

            self.write(
                f"bash: {str(e)}"
            )

        self.exit()
