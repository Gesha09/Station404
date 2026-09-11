   #!/bin/bash
   # Start the web server in the background
   echo "Starting Web Server..."
   python -m web.main &
   
   # Start the Discord bot in the foreground
   echo "Starting Discord Bot..."
   python -m bot.main