### Creating the movie agent

SMS is the first medium of communication

- The agent should be able to handle the following:
    - Identifying when a movie is being requested
    - Identifying the movie title and year
    - Identifying whether the movie already exists in the library
    - Idenfitying whether radarr has started downloading the movie
    - Identifying whether radarr was already downloading the movie
    - Monitor downloads and notify users when they start and complete
    - Notice the user when the download has completed and is ready to be watched
    - Notice when the movie being requested is not released yet, and inform the user of the release date
    
The agent will be monitoring a few things across the ecosystem, which means on it's periodic intervals it will be the one triggering actions, 
but it will also respond to user requests as they come in. 

The mechanism behind the agent will be that either when triggering an action, or when a user requests a movie, we will send
a openAI prompt that contains:
- The primary purpose of the agent
- Procecure that the agent should follow
- Each function the agent is allow to call as well as their description

and with this we will attach the new information that asks for an agentic decision.




