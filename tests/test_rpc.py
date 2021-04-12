class TestRPC(object):
    def test_import(self):
        from xray_rpc.app.stats.command import command_pb2_grpc as stats_command_pb2_grpc
        from xray_rpc.core import config_pb2

        assert issubclass(stats_command_pb2_grpc.StatsServiceStub, object)
        assert issubclass(config_pb2.Config, object)
