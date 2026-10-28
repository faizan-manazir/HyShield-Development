import socket

from cowrie.shell.command import HoneyPotCommand


class Command_bridge(HoneyPotCommand):

    def start(self):

        try:

            full_command = self.args

            if self.command:

                full_command = (
                    self.command
                    + " "
                    + self.args
                ).strip()

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

            if response:

                self.write(response)

            client.close()

        except Exception as e:

            self.write(
                f"bash: {str(e)}"
            )

        self.exit()
