import socket

from cowrie.shell.command import HoneyPotCommand


class Command_shell(HoneyPotCommand):

    def start(self):

        self.write(
            "Launching hybrid shell...\n"
        )

        while True:

            try:

                self.write(
                    "root@edge-gw-prod-01:$ "
                )

                line = self.protocol.terminal.readline()

                if not line:
                    break

                command = (
                    line.decode()
                    .strip()
                )

                if command in (
                    "exit",
                    "quit"
                ):

                    break

                client = socket.socket(
                    socket.AF_INET,
                    socket.SOCK_STREAM
                )

                client.connect(
                    ("127.0.0.1", 5050)
                )

                client.sendall(
                    command.encode()
                )

                response = client.recv(
                    65535
                ).decode()

                client.close()

                if response:

                    self.write(
                        response + "\n"
                    )

            except Exception as e:

                self.write(
                    f"bash: {str(e)}\n"
                )

                break

        self.exit()
