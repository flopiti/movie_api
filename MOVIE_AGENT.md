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
    - NOT IMPLEMENTED YET: Ask precision questions if the user is not clear on the movie they are requesting, and ask for confirmation is needed
    
The agent will be monitoring a few things across the ecosystem, which means on it's periodic intervals it will be the one triggering actions, 
but it will also respond to user requests as they come in. 

The mechanism behind the agent will be that either when triggering an action, or when a user requests a movie, we will send
a openAI prompt that contains:
- The primary purpose of the agent
- Procecure that the agent should follow
- Each function the agent is allow to call as well as their description

and with this we will attach the new information that asks for an agentic decision.


### Functions doing the work

1. process_agentic_response (agentic_service.py)

This function receives a conversation and will start a loop that will call functions, and from these calls it will receives data from which it 
might call other functions. 

2. generate_agentic_response (openai_client.py)

This function receives a prompt and will call the OpenAI API to generate a response that will be used by the process_agentic_response function.




