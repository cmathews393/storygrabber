# Storygrabber

## What is it?

Storygrabber is a self hosted docker container with simple configuration that allows for the pulling of your To-Read list from The StoryGraph and importing into LazyLibrarian. If TSG ever gets an API this will probably end up being deprecated but for now it should work.

## How to use it?

I'd STRONGLY recommend using the included docker compose file and a .env file ([How To](https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/#use-the-env_file-attribute)). The required environment variables are in the env.example file in this repo. Your storygraph profile must be public, I tried testing with authentication and ran into too many issues so for now at least thats unsupported.

If for whatever reason you don't want to use the docker compose, you will need a container with the storygrabber image, and a flaresolverr container/instance. If you have an existing FS instance, its probably easiest to just remove that from the compose and point the envvars to your existing instance, but I have not tested that so I can't say for sure whether it will work. Feel free to open an issue if it doesn't.
