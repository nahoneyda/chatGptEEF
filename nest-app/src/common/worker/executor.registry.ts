import { Inject, Injectable, OnModuleInit } from '@nestjs/common';
import { ModuleExecutor } from './module-executor.interface';
export const EF01_EXECUTOR=Symbol('EF01_EXECUTOR');
export const EF02_EXECUTOR=Symbol('EF02_EXECUTOR');
export const EF03_EXECUTOR=Symbol('EF03_EXECUTOR');
export const EF04_EXECUTOR=Symbol('EF04_EXECUTOR');
export const EF05_EXECUTOR=Symbol('EF05_EXECUTOR');
export const EF06_EXECUTOR=Symbol('EF06_EXECUTOR');
@Injectable()
export class ExecutorRegistry implements OnModuleInit{
  private readonly executors=new Map<string,ModuleExecutor>();
  constructor(
    @Inject(EF01_EXECUTOR) private readonly e1:ModuleExecutor,
    @Inject(EF02_EXECUTOR) private readonly e2:ModuleExecutor,
    @Inject(EF03_EXECUTOR) private readonly e3:ModuleExecutor,
    @Inject(EF04_EXECUTOR) private readonly e4:ModuleExecutor,
    @Inject(EF05_EXECUTOR) private readonly e5:ModuleExecutor,
    @Inject(EF06_EXECUTOR) private readonly e6:ModuleExecutor,
  ){}
  onModuleInit():void{[this.e1,this.e2,this.e3,this.e4,this.e5,this.e6].forEach(e=>this.register(e));}
  register(e:ModuleExecutor):void{if(this.executors.has(e.moduleCode))throw new Error(`Duplicate executor registration: ${e.moduleCode}`);this.executors.set(e.moduleCode,e);}
  get(code:string):ModuleExecutor{const e=this.executors.get(code);if(!e)throw new Error(`Executor not found: ${code}`);return e;}
  has(code:string):boolean{return this.executors.has(code);}
}
