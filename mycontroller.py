#!/usr/bin/env python3
import argparse
import os
import sys
from time import sleep

import grpc

# Import P4Runtime lib from parent utils dir
# Probably there's a better way of doing this.
sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 '../../utils/'))
import p4runtime_lib.bmv2
import p4runtime_lib.helper
from p4runtime_lib.error_utils import printGrpcError
from p4runtime_lib.switch import ShutdownAllSwitchConnections


def ipv4_forward(p4info_helper, ingress_sw, egress_sw,
                        dst_ip_addr,dst_num,dstAddr,port):
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ipv4_lpm",
        match_fields={
            "hdr.ipv4.dstAddr": (dst_ip_addr,dst_num)
        },
        action_name="MyIngress.ipv4_forward",
        action_params=
        {
            "dstAddr":dstAddr,
            "port":port
        })
    ingress_sw.WriteTableEntry(table_entry)



def readTableRules(p4info_helper, sw):
    """
    Reads the table entries from all tables on the switch.
    :param p4info_helper: the P4Info helper
    :param sw: the switch connection
    """
    print('\n----- Reading tables rules for %s -----' % sw.name)
    for response in sw.ReadTableEntries():
        for entity in response.entities:
            entry = entity.table_entry
            action = entry.action.action#读取动作实体
            action_name = p4info_helper.get_actions_name(action.action_id)#读取动作名
            #读取完成后，输出分析信息
            #对输入规则进行匹配
            for m in entry.match: #对已匹配过程中的所有实体使用p4info_helper进行翻译
                p4info_helper.get_match_field_name(table_name, m.field_id)
                p4info_helper.get_match_field_value(m)
            for p in action.params:
                p4info_helper.get_action_param_name(action_name, p.param_id)
            #分析动作体语句


def main(p4info_file_path, bmv2_file_path):
    # Instantiate a P4Runtime helper from the p4info file
    p4info_helper = p4runtime_lib.helper.P4InfoHelper(p4info_file_path)

    try:
        # Create a switch connection object for s1 and s2;
        # this is backed by a P4Runtime gRPC connection.
        # Also, dump all P4Runtime messages sent to switch to given txt files.
        s1 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s1',
            address='127.0.0.1:50051',
            device_id=0,
            proto_dump_file='logs/s1-p4runtime-requests.txt')
        s2 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s2',
            address='127.0.0.1:50052',
            device_id=1,
            proto_dump_file='logs/s2-p4runtime-requests.txt')
        s3 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s3',
            address='127.0.0.1:50053',
            device_id=3,
            proto_dump_file='logs/s3-p4runtime-requests.txt')    
        
        # Send master arbitration update message to establish this controller as
        # master (required by P4Runtime before performing any other write operation)
        s1.MasterArbitrationUpdate()
        s2.MasterArbitrationUpdate()
        s3.MasterArbitrationUpdate()

        # s1 流规则下发

        ipv4_forward(p4info_helper, s1, s1, 
        "10.0.1.1",32,"08:00:00:00:01:01",2)
        ipv4_forward(p4info_helper, s1, s1, 
        "10.0.1.11",32,"08:00:00:00:01:11",1)
        ipv4_forward(p4info_helper, s1, s1, 
        "10.0.2.0",24,"08:00:00:00:02:00",3)
        ipv4_forward(p4info_helper, s1, s1, 
        "10.0.3.0",24,"08:00:00:00:03:00",4)

        # s2 流规则下发
        ipv4_forward(p4info_helper, s2, s2, 
        "10.0.2.2",32,"08:00:00:00:02:02",2)
        ipv4_forward(p4info_helper, s2, s2, 
        "10.0.2.22",32,"08:00:00:00:02:22",1)
        ipv4_forward(p4info_helper, s2, s2, 
        "10.0.1.0",24,"08:00:00:00:01:00",3)
        ipv4_forward(p4info_helper, s2, s2, 
        "10.0.3.0",24,"08:00:00:00:03:00",4)

        
        # s3 流规则下发
        ipv4_forward(p4info_helper, s1, s1, 
        "10.0.3.3",32,"08:00:00:00:03:03",1)
        ipv4_forward(p4info_helper, s1, s1, 
        "10.0.1.0",24,"08:00:00:00:01:00",2)
        ipv4_forward(p4info_helper, s1, s1, 
        "10.0.2.0",24,"08:00:00:00:02:00",3)

        # 从s1,s2,s3中读取流表规则
        readTableRules(p4info_helper, s1)
        readTableRules(p4info_helper, s2)
        readTableRules(p4info_helper, s3)

        

    except KeyboardInterrupt:
        print(" Shutting down.")
    except grpc.RpcError as e:
        printGrpcError(e)

    ShutdownAllSwitchConnections()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='P4Runtime Controller')
    #qos实验的规则引入
    parser.add_argument('--p4info', help='p4info proto in text format from p4c',
                        type=str, action="store", required=False,
                        default='./build/qos.p4.p4info.txt')
    parser.add_argument('--bmv2-json', help='BMv2 JSON file from p4c',
                        type=str, action="store", required=False,
                        default='./build/qos.json')
    
    args = parser.parse_args()

    if not os.path.exists(args.p4info):
        parser.print_help()
        print("\np4info file not found: %s\nHave you run 'make'?" % args.p4info)
        parser.exit(1)
    if not os.path.exists(args.bmv2_json):
        parser.print_help()
        print("\nBMv2 JSON file not found: %s\nHave you run 'make'?" % args.bmv2_json)
        parser.exit(1)

    main(args.p4info, args.bmv2_json)
