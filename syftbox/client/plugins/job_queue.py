from syftbox.lib import Pipeline

initialized = False
pipelines = []


def create_job_pipeline(client_config):
    return Pipeline.make_job_pipeline(client_config)


def run_pipelines(client_config, pipelines):
    for pipeline in pipelines:
        print("> Running pipeline")
        pipeline.progress_pipeline(client_config)


def run(shared_state):
    global pipelines
    global initialized

    client_config = shared_state.client_config
    if not initialized:
        pipeline = create_job_pipeline(client_config)
        pipelines.append(pipeline)
        initialized = True
    else:
        run_pipelines(client_config, pipelines)
