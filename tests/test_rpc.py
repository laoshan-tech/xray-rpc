class TestRPC(object):
    def test_import(self):
        from xray_rpc.app.stats.command import command_pb2_grpc as stats_command_pb2_grpc

        assert issubclass(stats_command_pb2_grpc.StatsServiceStub, object)
