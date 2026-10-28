from cowrie.shell.command import HoneyPotCommand

import sys

sys.path.append("/home/faizan/cowrie/engine")

from api import process_command


class Command_hybrid(HoneyPotCommand):

    def start(self):

        full_command = self.args

        if self.command:

            full_command = (
                self.command
                + " "
                + self.args
            ).strip()

        try:

            output = process_command(
                full_command
            )

            if output:

                self.write(output)

        except Exception as e:

            self.write(
                f"bash: {str(e)}"
            )

        self.exit()
