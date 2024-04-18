# TODO need to update this so it is actually calling cloudcap - files are passed in as strings in the POST request?

def lambda_handler(event, context):
    message = 'Hello {} {}!'.format(event['first_name'], event['last_name'])  
    return { 
        'message' : message
    }
